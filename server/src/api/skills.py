"""Skills REST 端点（Phase 6.4）。

端点：
- GET  /skills              列出所有已注册 skill
- POST /skills/{name}/run   执行（body 是 skill 的 input kwargs）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ..core.skills import registry, run_skill
from ..core.skills.base import Skill
from ..core.skills.registry import SkillNotFoundError


class SkillSummary(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    requires_llm: bool


class RunSkillRequest(BaseModel):
    """Skill run 请求体（任意字段，对应 input_schema）。"""

    model_config = ConfigDict(extra="allow")


class SkillResultResponse(BaseModel):
    success: bool
    data: dict[str, Any] = {}
    error: str | None = None


router = APIRouter(prefix="/skills", tags=["skills"])


def _skill_to_summary(s: Skill) -> SkillSummary:
    return SkillSummary(
        name=s.name,
        description=s.description,
        input_schema=s.input_schema,
        requires_llm=s.requires_llm,
    )


@router.get(
    "",
    response_model=list[SkillSummary],
    summary="列出所有已注册 skill（Phase 6.4）",
)
def list_skills_endpoint() -> list[SkillSummary]:
    return [_skill_to_summary(s) for s in registry.list()]


@router.post(
    "/{name}/run",
    response_model=SkillResultResponse,
    summary="执行一个 skill（body 是 skill 的输入字段）",
)
async def run_skill_endpoint(name: str, payload: RunSkillRequest) -> SkillResultResponse:
    try:
        result = await run_skill(name, **payload.model_dump(exclude_unset=True))
    except SkillNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SkillResultResponse(
        success=result.success, data=result.data, error=result.error
    )


__all__ = ["router"]
