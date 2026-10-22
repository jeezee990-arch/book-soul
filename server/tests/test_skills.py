"""Skill 系统测试（Phase 6.4）。

覆盖：
- base.Skill / SkillResult 协议
- registry.register / get / list / run
- builtin: word_counter / sensitive_word
- API: GET /skills / POST /skills/{name}/run
"""

from __future__ import annotations

import pytest

# ===== base =====


def test_skill_result_success() -> None:
    from src.core.skills.base import SkillResult

    r = SkillResult(success=True, data={"x": 1})
    assert r.success is True
    assert r.data == {"x": 1}
    assert r.error is None


def test_skill_result_failure() -> None:
    from src.core.skills.base import SkillResult

    r = SkillResult(success=False, error="oops")
    assert r.success is False
    assert r.error == "oops"


# ===== registry =====


def test_registry_register_and_get() -> None:
    from src.core.skills.base import SkillResult
    from src.core.skills.registry import SkillRegistry

    class FakeSkill:
        name = "fake"
        description = "fake skill"
        input_schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        }
        requires_llm = False

        async def execute(self, x: int) -> SkillResult:  # type: ignore[override]
            return SkillResult(success=True, data={"doubled": x * 2})

    reg = SkillRegistry()
    s = FakeSkill()
    reg.register(s)
    assert reg.has("fake")
    assert reg.get("fake") is s
    assert len(reg.list()) == 1


def test_registry_get_not_found() -> None:
    from src.core.skills.registry import SkillNotFoundError, SkillRegistry

    reg = SkillRegistry()
    with pytest.raises(SkillNotFoundError):
        reg.get("nope")


@pytest.mark.asyncio
async def test_registry_run_success() -> None:
    from src.core.skills.base import SkillResult
    from src.core.skills.registry import SkillRegistry

    class FakeSkill:
        name = "fake"
        description = ""
        input_schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        }
        requires_llm = False

        async def execute(self, x: int) -> SkillResult:
            return SkillResult(success=True, data={"y": x + 1})

    reg = SkillRegistry()
    reg.register(FakeSkill())
    result = await reg.run("fake", x=10)
    assert result.success is True
    assert result.data == {"y": 11}


@pytest.mark.asyncio
async def test_registry_run_missing_field() -> None:
    from src.core.skills.base import SkillResult
    from src.core.skills.registry import SkillRegistry

    class FakeSkill:
        name = "fake"
        description = ""
        input_schema = {"type": "object", "required": ["x"]}
        requires_llm = False

        async def execute(self, **kw) -> SkillResult:
            return SkillResult(success=True)

    reg = SkillRegistry()
    reg.register(FakeSkill())
    result = await reg.run("fake")  # 缺 x
    assert result.success is False
    assert "Missing" in (result.error or "")


@pytest.mark.asyncio
async def test_registry_run_execution_error() -> None:
    from src.core.skills.base import SkillResult
    from src.core.skills.registry import SkillRegistry

    class BuggySkill:
        name = "bug"
        description = ""
        input_schema = {"type": "object"}
        requires_llm = False

        async def execute(self) -> SkillResult:
            raise RuntimeError("kaboom")

    reg = SkillRegistry()
    reg.register(BuggySkill())
    result = await reg.run("bug")
    assert result.success is False
    assert "kaboom" in (result.error or "")


def test_registry_builtin_auto_register() -> None:
    """import 触发 builtin skills 自动注册。"""
    from src.core.skills import list_skills

    skills = list_skills()
    names = [s.name for s in skills]
    assert "word_counter" in names
    assert "sensitive_word" in names


# ===== word_counter =====


@pytest.mark.asyncio
async def test_word_counter_chinese_only() -> None:
    from src.core.skills import run_skill

    r = await run_skill("word_counter", text="韩立出身凡人")
    assert r.success is True
    assert r.data["chinese_chars"] == 6
    assert r.data["english_words"] == 0
    assert r.data["total"] == 6


@pytest.mark.asyncio
async def test_word_counter_english_only() -> None:
    from src.core.skills import run_skill

    r = await run_skill("word_counter", text="hello world foo bar")
    assert r.success is True
    assert r.data["chinese_chars"] == 0
    assert r.data["english_words"] == 4
    assert r.data["total"] == 4


@pytest.mark.asyncio
async def test_word_counter_mixed() -> None:
    from src.core.skills import run_skill

    r = await run_skill("word_counter", text="韩立 出生 hello 凡人 123")
    assert r.success is True
    # 中文字符：韩/立/出/生/凡/人 = 6
    # split 后 tokens: "韩立" "出生" "hello" "凡人" "123"（5 个）
    # english = "hello"（有字母）= 1
    # numbers = "123"（纯数字）= 1
    # chinese 按 char 算 = 6
    assert r.data["chinese_chars"] == 6
    assert r.data["english_words"] == 1
    assert r.data["numbers"] == 1


@pytest.mark.asyncio
async def test_word_counter_empty() -> None:
    from src.core.skills import run_skill

    r = await run_skill("word_counter", text="")
    assert r.success is True
    assert r.data["total"] == 0


# ===== sensitive_word =====


@pytest.mark.asyncio
async def test_sensitive_word_no_match() -> None:
    from src.core.skills import run_skill

    r = await run_skill("sensitive_word", text="普通文本，无敏感内容")
    assert r.success is True
    assert r.data["has_sensitive"] is False
    assert r.data["matches"] == []


@pytest.mark.asyncio
async def test_sensitive_word_match() -> None:
    from src.core.skills import run_skill

    r = await run_skill("sensitive_word", text="这里出现赌博字样")
    assert r.success is True
    assert r.data["has_sensitive"] is True
    assert any(m["word"] == "赌博" for m in r.data["matches"])


@pytest.mark.asyncio
async def test_sensitive_word_custom_words() -> None:
    from src.core.skills import run_skill

    r = await run_skill("sensitive_word", text="hello world", words=["hello"])
    assert r.success is True
    assert r.data["has_sensitive"] is True
    assert r.data["matches"][0]["word"] == "hello"
    assert r.data["checked"] == 1


@pytest.mark.asyncio
async def test_sensitive_word_empty() -> None:
    from src.core.skills import run_skill

    r = await run_skill("sensitive_word", text="")
    assert r.success is True
    assert r.data["has_sensitive"] is False


# ===== API =====


def test_api_list_skills() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.get("/skills")
    assert resp.status_code == 200
    body = resp.json()
    names = [s["name"] for s in body]
    assert "word_counter" in names
    assert "sensitive_word" in names


def test_api_run_skill_word_counter() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/skills/word_counter/run", json={"text": "韩立测试"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["chinese_chars"] == 4


def test_api_run_skill_not_found() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/skills/nope/run", json={})
    assert resp.status_code == 404


def test_api_run_skill_missing_field() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/skills/word_counter/run", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "Missing" in body["error"]
