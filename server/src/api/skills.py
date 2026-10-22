"""Skills REST 端点（Phase 6.4 + Phase Skills 自动化）。

端点：
- GET  /skills                          列出（带 manifest：source / enabled / triggers / type）
- POST /skills/{name}/enable            启用
- POST /skills/{name}/disable           禁用
- POST /skills/{name}/run               执行（debug 用）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..core.skills import manager as skill_manager
from ..core.skills import registry, run_skill
from ..core.skills.base import Skill
from ..core.skills.manager import list_for_scene
from ..core.skills.registry import SkillNotFoundError


class SkillSummary(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    requires_llm: bool


class SkillStatus(BaseModel):
    """完整 skill 状态（前端 Skills 页用）。"""

    name: str
    description: str
    requires_llm: bool
    input_schema: dict[str, Any]
    source: str = Field(default="builtin")  # builtin | user
    enabled: bool = True
    apply_type: str = "post_process"
    triggers: list[str] = Field(default_factory=list)


class RunSkillRequest(BaseModel):
    """Skill run 请求体（任意字段，对应 input_schema）。"""

    model_config = ConfigDict(extra="allow")


class SkillResultResponse(BaseModel):
    success: bool
    data: dict[str, Any] = {}
    error: str | None = None


def _skill_to_summary(s: Skill) -> SkillSummary:
    return SkillSummary(
        name=s.name,
        description=s.description,
        input_schema=s.input_schema,
        requires_llm=s.requires_llm,
    )


def _skill_to_status(s: Skill) -> SkillStatus:
    manifest = getattr(s, "_manifest", {}) or {}
    return SkillStatus(
        name=s.name,
        description=s.description,
        requires_llm=s.requires_llm,
        input_schema=s.input_schema,
        source=manifest.get("source", "builtin"),
        enabled=bool(manifest.get("enabled", True)),
        apply_type=str(manifest.get("type", "post_process")),
        triggers=list(manifest.get("triggers") or []),
    )


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get(
    "",
    response_model=list[SkillStatus],
    summary="列出所有已注册 skill（含 manifest 状态）",
)
def list_skills_endpoint() -> list[SkillStatus]:
    return [_skill_to_status(s) for s in registry.list()]


@router.post(
    "/{name}/enable",
    response_model=SkillStatus,
    summary="启用 skill（恢复自动调用）",
)
def enable_skill_endpoint(name: str) -> SkillStatus:
    if not skill_manager.enable(name):
        raise HTTPException(status_code=404, detail=f"Skill not found: {name!r}")
    return _skill_to_status(registry.get(name))


@router.post(
    "/{name}/disable",
    response_model=SkillStatus,
    summary="禁用 skill（停止自动调用，但仍保留在注册表）",
)
def disable_skill_endpoint(name: str) -> SkillStatus:
    if not skill_manager.disable(name):
        raise HTTPException(status_code=404, detail=f"Skill not found: {name!r}")
    return _skill_to_status(registry.get(name))


@router.get(
    "/scene/{scene}",
    response_model=list[str],
    summary="列出指定场景会自动调用的 skill 名",
)
def list_for_scene_endpoint(scene: str) -> list[str]:
    return list_for_scene(scene)


@router.post(
    "/{name}/run",
    response_model=SkillResultResponse,
    summary="执行一个 skill（debug 用；正常场景无需手动调用）",
)
async def run_skill_endpoint(name: str, payload: RunSkillRequest) -> SkillResultResponse:
    try:
        result = await run_skill(name, **payload.model_dump(exclude_unset=True))
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SkillResultResponse(success=result.success, data=result.data, error=result.error)


__all__ = ["router"]
