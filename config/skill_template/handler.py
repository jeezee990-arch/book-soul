"""Skill 模板 — 复制整个目录到 ``data/skills/<你的名字>/`` 即可预装。

约定：
- 文件夹下必须有 ``manifest.yaml`` + ``handler.py``
- handler 必须暴露 ``create_skill() -> Skill`` 工厂
- ``Skill.name`` 必须与 ``manifest.yaml`` 的 ``name`` 一致

后端会在启动时自动 ``importlib`` 这个文件 + 注册到 registry；
之后所有匹配的 scene 在 LLM 流式输出完成后会自动调用 ``skill.execute(text=...)``。
"""

from __future__ import annotations

from typing import Any

from ...base import Skill, SkillResult
from ...loader import BUILTIN_MANIFESTS  # noqa: F401  -- 示例：可复用内置 manifest 配置


class MyCustomSkill:
    """示例 skill：把文本里所有感叹号换成句号。"""

    name = "my_custom_skill"
    description = "把感叹号换成句号（示例）"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, *, text: str = "", **_: Any) -> SkillResult:
        if not text:
            return SkillResult(success=True, data={"text": text})
        new_text = text.replace("！", "。").replace("!", ".")
        return SkillResult(success=True, data={"text": new_text})


def create_skill() -> Skill:
    return MyCustomSkill()  # type: ignore[return-value]
