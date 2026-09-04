"""词库 REST 端点（Phase 3.1）。

端点：
- GET /wordbanks                       → WordbankList         题材列表（id/name/total）
- GET /wordbanks/{genre}               → WordbankMeta         题材元数据
- GET /wordbanks/{genre}/words         → list[str] | dict     随机取词
    - 单类：``?category=themes&n=10``     → ``[word, ...]``
    - 多类：``?category=themes&category=plots&n=10`` → ``{themes: [...], plots: [...]}``

错误映射：
- WordbankNotFoundError   → 404
- WordbankValidationError → 422
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.wordbank import WordbankList, WordbankListEntry, WordbankMeta
from ..services.wordbank_service import (
    WordbankNotFoundError,
    WordbankService,
    WordbankValidationError,
)

router = APIRouter(prefix="/wordbanks", tags=["wordbanks"])

_service = WordbankService()


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
