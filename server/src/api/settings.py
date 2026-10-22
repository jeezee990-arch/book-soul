"""Settings REST 端点（Phase 2.4）。

端点：
- GET    /settings                    读取设置（包含哪些 provider 已存 key）
- PUT    /settings                    部分更新（合并到 yaml）
- POST   /settings/api-key/{provider}  保存 API key（DPAPI 加密文件优先，keyring 降级）
- DELETE /settings/api-key/{provider}  删除 API key（幂等）

API Key 永远不出现在响应里，只通过 api_key_configured 字典告知是否存在。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from ..core.llm.factory import clear_llm_client_cache
from ..schemas.settings import APIKeyUpdate, SettingsRead, SettingsUpdate
from ..services.settings_service import (
    SettingsService,
    SettingsServiceError,
    SettingsValidationError,
)

router = APIRouter(prefix="/settings", tags=["settings"])

_PROVIDER_PATH_DESC = "provider name: mimo/minimax/openai/ollama"


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
        result = service.update(payload)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    # 换 provider / 模型后，缓存的 LLM client（带旧 provider+model）要作废
    clear_llm_client_cache()
    return result


@router.post(
    "/api-key/{provider}",
    response_model=SettingsRead,
    summary="保存 API key（DPAPI 加密文件优先，系统凭据管理器降级）",
)
async def set_api_key(
    provider: str = Path(..., description=_PROVIDER_PATH_DESC),
    payload: APIKeyUpdate = ...,
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    try:
        service.set_api_key(provider, payload.key)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SettingsServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    # 新 key 写入：清掉缓存的 LLM client（让下次请求用新 key）
    clear_llm_client_cache()
    return service.get()


@router.delete(
    "/api-key/{provider}",
    response_model=SettingsRead,
    summary="删除 API key（幂等）",
)
async def delete_api_key(
    provider: str = Path(..., description=_PROVIDER_PATH_DESC),
    service: SettingsService = Depends(get_service),
) -> SettingsRead:
    try:
        service.delete_api_key(provider)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    clear_llm_client_cache()
    return service.get()
