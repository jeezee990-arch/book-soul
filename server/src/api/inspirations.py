"""灵感 REST 端点（Phase 1.5 + Phase 3.3）。

端点：
- POST   /inspirations                  创建（novel_id 可空）
- GET    /inspirations                  列表（filter: novel_id, type, tag）
- GET    /inspirations/{id}             详情
- PATCH  /inspirations/{id}             部分更新
- DELETE /inspirations/{id}             删除（幂等）
- POST   /inspirations/generate-plot    Phase 3.3 剧情生成（不入库）
- POST   /inspirations/generate-plot/stream  流式剧情生成（ndjson）

错误映射：
- InspirationNotFoundError / NovelNotFoundError -> 404
- InspirationValidationError -> 422
- PlotGenerationError -> 500（LLM 失败）/ 422（参数错）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.inspiration import (
    InspirationCreate,
    InspirationRead,
    InspirationUpdate,
    PlotGenerationRequest,
    PlotGenerationResponse,
    PlotVersion,
)
from ..services.inspiration_service import (
    InspirationNotFoundError,
    InspirationService,
    InspirationValidationError,
    NovelNotFoundError,
    PlotGenerationError,
    PlotService,
)
from ._stream_helpers import ndjson_line, ndjson_response

router = APIRouter(prefix="/inspirations", tags=["inspirations"])


def get_service(session: AsyncSession = Depends(get_db)) -> InspirationService:
    return InspirationService(session)


@router.post(
    "",
    response_model=InspirationRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建灵感（novel_id 可空，content 按 type 校验）",
)
async def create_inspiration(
    payload: InspirationCreate,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.create(payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.get(
    "",
    response_model=list[InspirationRead],
    summary="列出灵感（filter: novel_id, type, tag）",
)
async def list_inspirations(
    novel_id: int | None = Query(default=None, description="按作品 id 过滤（None=仅通用）"),
    type_filter: str | None = Query(default=None, alias="type", description="按类型过滤"),
    tag: str | None = Query(default=None, description="按 tag 过滤（精确匹配）"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: InspirationService = Depends(get_service),
) -> list[InspirationRead]:
    try:
        inspirations = await service.list_all(
            novel_id=novel_id,
            inspiration_type=type_filter,
            tag=tag,
            limit=limit,
            offset=offset,
        )
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [InspirationRead.model_validate(i) for i in inspirations]


@router.get(
    "/{inspiration_id}",
    response_model=InspirationRead,
    summary="获取灵感详情",
)
async def get_inspiration(
    inspiration_id: int,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.get(inspiration_id)
    except InspirationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.patch(
    "/{inspiration_id}",
    response_model=InspirationRead,
    summary="部分更新灵感",
)
async def update_inspiration(
    inspiration_id: int,
    payload: InspirationUpdate,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.update(inspiration_id, payload)
    except InspirationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.delete(
    "/{inspiration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除灵感（幂等）",
)
async def delete_inspiration(
    inspiration_id: int,
    service: InspirationService = Depends(get_service),
) -> None:
    try:
        await service.delete(inspiration_id)
    except InspirationNotFoundError:
        return  # 幂等


# ===== Phase 3.3：剧情生成（不入库）=====


# 注意：路径在 ``/{inspiration_id}`` 之前注册，避免被 path param 吞掉
@router.post(
    "/generate-plot",
    response_model=PlotGenerationResponse,
    summary="生成简要剧情（不入库；调 LLM 抽象）",
)
async def generate_plot(
    payload: PlotGenerationRequest,
) -> PlotGenerationResponse:
    """生成 n 个简要剧情版本，供前端选一个后保存到 inspirations。"""
    svc = PlotService()
    try:
        summaries = await svc.generate(
            genre=payload.genre,
            keywords=payload.keywords,
            n_versions=payload.n_versions,
        )
    except PlotGenerationError as e:
        # LLM 失败 → 500；参数错（Pydantic 已经 422 拦了大部分）
        raise HTTPException(status_code=500, detail=str(e)) from e
    versions = [PlotVersion(index=i + 1, summary=s) for i, s in enumerate(summaries)]
    # 取 provider / model 信息（用 _get_llm 不重新创建）
    try:
        llm = svc._get_llm()  # noqa: SLF001
        provider = getattr(llm, "provider", "unknown")
        model = getattr(llm, "model", "")
    except Exception:  # noqa: BLE001
        provider = "unknown"
        model = ""
    return PlotGenerationResponse(versions=versions, provider=provider, model=model)


# ===== 流式版本（Phase 性能优化）=====


@router.post(
    "/generate-plot/stream",
    summary="流式生成简要剧情（ndjson；多版本实时 ticker-by-tick）",
)
async def generate_plot_stream(payload: PlotGenerationRequest):
    """流式端点：每个版本独立并行；前端按 ndjson 行解析。

    协议见 :mod:`src.api._stream_helpers`。
    """
    svc = PlotService()

    async def gen():
        async for event in svc.stream_generate(
            genre=payload.genre,
            keywords=payload.keywords,
            n_versions=payload.n_versions,
            user_extra=payload.user_extra,
        ):
            yield ndjson_line(event)

    return ndjson_response(gen())


# ===== Phase 6.1：灵感详情（含关联作品的人物卡/大纲/章节摘要）=====


async def _build_novel_summary(session: AsyncSession, novel_id: int):
    """构造 :class:`NovelContextSummary`；没有该 novel 时返回 None。"""
    # 延迟 import 避免循环
    from ..models.chapter import Chapter
    from ..models.character import Character
    from ..models.novel import Novel
    from ..models.outline import Outline
    from ..schemas.inspiration import (
        ChapterSummary,
        CharacterSummary,
        NovelContextSummary,
    )

    novel = await session.get(Novel, novel_id)
    if novel is None:
        return None
    # 人物卡
    chars_stmt = (
        select(Character)
        .where(Character.novel_id == novel_id)
        .order_by(Character.role.asc(), Character.id.asc())
    )
    chars = list((await session.execute(chars_stmt)).scalars())
    char_summaries = [
        CharacterSummary(
            id=c.id,
            name=c.name,
            role=c.role,
            personality=c.personality,
            is_active=c.is_active,
        )
        for c in chars
    ]
    # 大纲（取最新一条）
    outline_stmt = (
        select(Outline).where(Outline.novel_id == novel_id).order_by(Outline.id.desc()).limit(1)
    )
    outline = (await session.execute(outline_stmt)).scalar_one_or_none()
    # 章节
    ch_stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number.asc(), Chapter.id.asc())
    )
    chs = list((await session.execute(ch_stmt)).scalars())
    ch_summaries = [
        ChapterSummary(
            id=c.id,
            chapter_number=c.chapter_number,
            title=c.title,
            word_count=c.word_count,
            status=c.status,
        )
        for c in chs
    ]
    return NovelContextSummary(
        id=novel.id,
        name=novel.name,
        genre=novel.genre,
        outline_type=novel.outline_mode,
        description=novel.description,
        outline_structure=outline.structure if outline else None,
        characters=char_summaries,
        chapters=ch_summaries,
    )


@router.get(
    "/{inspiration_id}/detail",
    response_model=None,  # forward ref by name（避免循环 import）
    summary="Phase 6.1：灵感详情（含关联作品的人物卡/大纲/章节摘要）",
)
async def get_inspiration_detail(
    inspiration_id: int,
    session: AsyncSession = Depends(get_db),
    service: InspirationService = Depends(get_service),
):
    from ..schemas.inspiration import InspirationDetailRead

    try:
        inspiration = await service.get(inspiration_id)
    except InspirationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    novel_summary = None
    if inspiration.novel_id is not None:
        novel_summary = await _build_novel_summary(session, inspiration.novel_id)

    return InspirationDetailRead(
        id=inspiration.id,
        novel_id=inspiration.novel_id,
        type=inspiration.type,
        source=inspiration.source,
        tags=list(inspiration.tags or []),
        content=dict(inspiration.content or {}),
        created_at=inspiration.created_at,
        novel=novel_summary,
    )
