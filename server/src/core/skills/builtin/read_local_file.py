"""读本地文件 Skill（Phase 7.1）。

安全读取 .md / .txt 文件（限制大小 + 路径检查）。
"""

from __future__ import annotations

from pathlib import Path

from ..base import SkillResult

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_SUFFIXES = {".md", ".txt", ".markdown"}
ALLOWED_DIR_PREFIXES: tuple[str, ...] = ()  # 留空 = 不限制目录（用户授权后用）


class ReadLocalFileSkill:
    name = "read_local_file"
    description = "安全读取本地 .md / .txt 文件（≤5MB）"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件绝对路径"},
        },
        "required": ["path"],
    }
    requires_llm = False

    async def execute(self, path: str) -> SkillResult:
        if not isinstance(path, str) or not path.strip():
            return SkillResult(success=False, error="path is required")

        p = Path(path)
        if not p.is_file():
            return SkillResult(success=False, error=f"Not a file: {path}")
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            return SkillResult(
                success=False,
                error=f"Disallowed suffix {p.suffix!r}; allowed: {sorted(ALLOWED_SUFFIXES)}",
            )
        # 大小限制
        try:
            size = p.stat().st_size
        except OSError as e:
            return SkillResult(success=False, error=f"stat failed: {e}")
        if size > MAX_BYTES:
            return SkillResult(
                success=False,
                error=f"File too large: {size} bytes (max {MAX_BYTES})",
            )

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            return SkillResult(success=False, error=f"read failed: {e}")

        return SkillResult(
            success=True,
            data={"path": str(p.absolute()), "size": size, "content": content},
        )


__all__ = ["ReadLocalFileSkill"]
