"""词库 REST 端点（Phase 3.1 读 / 需求6 读写管理）。

端点：
- GET /wordbanks                       → WordbankList         题材列表（id/name/total）
- GET /wordbanks/{genre}               → WordbankMeta         题材元数据
- GET /wordbanks/{genre}/words         → list[str] | dict     随机取词
    - 单类：``?category=themes&n=10``     → ``[word, ...]``
    - 多类：``?category=themes&category=plots&n=10`` → ``{themes: [...], plots: [...]}``
- GET /wordbanks/{genre}/all-words     → WordbankAllWords     该板块全部词条
- POST /wordbanks/{genre}/words        → WordbankMutationResult  新增（单个/批量）
- PATCH /wordbanks/{genre}/words       → WordbankMutationResult  修改
- DELETE /wordbanks/{genre}/words      → WordbankMutationResult  删除（支持批量）
- POST /wordbanks/{genre}/import       → WordbankImportResult  粘贴文本导入
- POST /wordbanks/{genre}/import-file  → WordbankImportResult  文件导入（原始 body）

错误映射：
- WordbankNotFoundError   → 404
- WordbankValidationError → 422

板块隔离：每个写操作只带**一个** genre 参数，只能改那个板块自己的 YAML。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..schemas.wordbank import (
    WordbankAllWords,
    WordbankImportRequest,
    WordbankImportResult,
    WordbankList,
    WordbankListEntry,
    WordbankMeta,
    WordbankMutationResult,
    WordsAddRequest,
    WordsDeleteRequest,
    WordUpdateRequest,
)
from ..services.wordbank_service import (
    WordbankNotFoundError,
    WordbankService,
    WordbankValidationError,
)

router = APIRouter(prefix="/wordbanks", tags=["wordbanks"])

_service = WordbankService()

# 导入文件大小上限（1 MiB）—— 种子词是纯文本，超过这个量基本是粘错了
MAX_IMPORT_BYTES = 1024 * 1024


@router.get(
    "",
    response_model=WordbankList,
    summary="列出所有题材（id/name/total）",
)
async def list_wordbanks() -> WordbankList:
    genres = _service.list_genres()
    return WordbankList(genres=[WordbankListEntry(**g) for g in genres])


@router.get(
    "/{genre}",
    response_model=WordbankMeta,
    summary="获取题材元数据（name + categories + counts）",
)
async def get_wordbank(genre: str) -> WordbankMeta:
    try:
        meta = _service.get_metadata(genre)
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return WordbankMeta(**meta)


@router.get(
    "/{genre}/words",
    summary="从词库随机取词（单类返回 list；多类返回 dict）",
    response_model=list[str] | dict[str, list[str]],  # type: ignore[return-value]
)
async def get_random_words(
    genre: str,
    category: list[str] = Query(  # noqa: B008
        ..., description="分类名（必填；可重复传多值）"
    ),
    n: int = Query(default=10, ge=1, le=100, description="每个分类的抽样数"),
) -> list[str] | dict[str, list[str]]:
    if not category:
        raise HTTPException(
            status_code=422,
            detail="Query param 'category' is required",
        )
    try:
        if len(category) == 1:
            return _service.get_random_words(genre, category[0], n)
        return _service.get_random_words_multi(genre, dict.fromkeys(category, n))
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get(
    "/{genre}/all-words",
    response_model=WordbankAllWords,
    summary="获取该板块的全部词条（按分类分组）",
)
async def get_all_words(genre: str) -> WordbankAllWords:
    """词库管理弹窗用：一次拿全该板块的词，不用分页。

    注意路径是 ``all-words`` 而不是 ``words`` —— 后者已经被"随机取词"占了。
    """
    try:
        meta = _service.get_metadata(genre)
        words = _service.get_all_words(genre)
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return WordbankAllWords(
        id=meta["id"],
        name=meta["name"],
        categories=meta["categories"],
        words=words,
        counts=meta["counts"],
    )


@router.post(
    "/{genre}/words",
    response_model=WordbankMutationResult,
    summary="新增词条（单个或批量）",
)
async def add_words(genre: str, body: WordsAddRequest) -> WordbankMutationResult:
    try:
        result = _service.add_words(genre, [(i.category, i.word) for i in body.items])
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return WordbankMutationResult(
        added=result.added,
        updated=result.updated,
        deleted=result.deleted,
        duplicates=result.duplicates,
        errors=result.errors,
        missing=result.missing,
    )


@router.patch(
    "/{genre}/words",
    response_model=WordbankMutationResult,
    summary="修改词条（category + old → new）",
)
async def update_word(genre: str, body: WordUpdateRequest) -> WordbankMutationResult:
    try:
        result = _service.update_word(genre, body.category, body.old, body.new)
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return WordbankMutationResult(
        added=result.added,
        updated=result.updated,
        deleted=result.deleted,
        duplicates=result.duplicates,
        errors=result.errors,
        missing=result.missing,
    )


@router.delete(
    "/{genre}/words",
    response_model=WordbankMutationResult,
    summary="删除词条（支持批量）",
)
async def delete_words(genre: str, body: WordsDeleteRequest) -> WordbankMutationResult:
    try:
        result = _service.delete_words(genre, [(i.category, i.word) for i in body.items])
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return WordbankMutationResult(
        added=result.added,
        updated=result.updated,
        deleted=result.deleted,
        duplicates=result.duplicates,
        errors=result.errors,
        missing=result.missing,
    )


@router.post(
    "/{genre}/import",
    response_model=WordbankImportResult,
    summary="导入词条（粘贴文本）",
)
async def import_words(genre: str, body: WordbankImportRequest) -> WordbankImportResult:
    try:
        report = _service.import_words(genre, body.text, body.default_category)
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return WordbankImportResult(
        added=report.added,
        duplicates=report.duplicates,
        failed=report.failed,
        errors=report.errors,
        by_category=report.by_category,
    )


@router.post(
    "/{genre}/import-file",
    response_model=WordbankImportResult,
    summary="导入词条（文件，原始 body）",
)
async def import_words_file(
    genre: str,
    request: Request,
    default_category: str = Query(default="themes", description="没写分类前缀的词归到哪类"),
) -> WordbankImportResult:
    """上传文本文件导入。

    ⚠️ 这里刻意**不用** ``UploadFile``：那需要 ``python-multipart`` 依赖，
    而种子词就是一个纯文本文件，前端直接把文件内容当 body 发过来更简单，
    也不用给打包版多加一个第三方依赖。

    文件内容**只进内存、从不落盘** —— 所以不存在路径越界的问题；
    大小上限 1 MiB（超了 413）。
    """
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > MAX_IMPORT_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大（上限 {MAX_IMPORT_BYTES // 1024} KiB）",
            )
    try:
        text = buffer.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=422,
            detail=f"文件不是 UTF-8 文本：{e}",
        ) from e

    try:
        report = _service.import_words(genre, text, default_category)
    except WordbankNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WordbankValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return WordbankImportResult(
        added=report.added,
        duplicates=report.duplicates,
        failed=report.failed,
        errors=report.errors,
        by_category=report.by_category,
    )
