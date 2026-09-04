"""Settings REST 端点（Phase 2.4）。

端点：
- GET    /settings                    读取设置（包含哪些 provider 已存 key）
- PUT    /settings                    部分更新（合并到 yaml）
- POST   /settings/api-key/{provider}  保存 API key 到 keyring
- DELETE /settings/api-key/{provider}  删除 keyring 中的 key（幂等）

API Key 永远不出现在响应里，只通过 api_key_configured 字典告知是否存在。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from ..schemas.settings import APIKeyUpdate, SettingsRead, SettingsUpdate
from ..services.settings_service import (
    SettingsService,
    SettingsServiceError,
    SettingsValidationError,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def get_service() -> SettingsService:
    """单例 service（无 DB 依赖，无 async 状态）。"""
    return SettingsService()


@router.get(
    "",
    response_model=SettingsRead,
    summary="读取运行时设置",
)
async def get_settings(
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    return service.get()


@router.put(
    "",
    response_model=SettingsRead,
    summary="更新运行时设置（部分合并）",
)
async def update_settings(
    payload: SettingsUpdate,
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    try:
        return service.update(payload)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post(
    "/api-key/{provider}",
    response_model=SettingsRead,
    summary="保存 API key 到系统 keyring",
)
async def set_api_key(
    provider: str = Path(..., description="provider name: minimax/openai/ollama"),
    payload: APIKeyUpdate = ...,
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    try:
        service.set_api_key(provider, payload.key)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SettingsServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return service.get()


@router.delete(
    "/api-key/{provider}",
    response_model=SettingsRead,
    summary="删除 keyring 中的 API key（幂等）",
)
async def delete_api_key(
    provider: str = Path(..., description="provider name: minimax/openai/ollama"),
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    try:
        service.delete_api_key(provider)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return service.get()
