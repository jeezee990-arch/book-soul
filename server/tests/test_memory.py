"""测试 memory 子包（Phase 1.7）。

覆盖：
- ProjectMemory stub：所有方法返回合理默认值，不抛错
- RagMemory stub：add 返回 string id，search 返回空 list
- ConversationMemory 真实现：add/get/clear/truncate/边界
"""

from __future__ import annotations

import pytest

# ===== ProjectMemory（stub）=====


@pytest.mark.asyncio
async def test_project_memory_get_context_returns_empty_dict():
    """stub 阶段 get_context 应返回空 dict。"""
    from src.core.memory.project_memory import ProjectMemory

    mem = ProjectMemory(novel_id=1)
    ctx = await mem.get_context()
    assert ctx == {}


@pytest.mark.asyncio
async def test_project_memory_add_note_is_noop():
    """stub 阶段 add_note 不抛错。"""
    from src.core.memory.project_memory import ProjectMemory

    mem = ProjectMemory(novel_id=1)
    await mem.add_note("weakness", "主角弱点是 X")
    # 不抛错即可；无返回值


@pytest.mark.asyncio
async def test_project_memory_get_notes_returns_empty():
    from src.core.memory.project_memory import ProjectMemory

    mem = ProjectMemory(novel_id=1)
    notes = await mem.get_notes()
    assert notes == {}


@pytest.mark.asyncio
async def test_project_memory_clear_is_noop():
    from src.core.memory.project_memory import ProjectMemory

    mem = ProjectMemory(novel_id=1)
    await mem.clear()


# ===== RagMemory（stub）=====


@pytest.mark.asyncio
async def test_rag_memory_add_returns_string_id():
    """stub 阶段 add 返回 string id。"""
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    rid = await rag.add("一段文本", metadata={"chapter": 1})
    assert isinstance(rid, str)
    assert len(rid) > 0


@pytest.mark.asyncio
async def test_rag_memory_add_with_custom_id():
    """自定义 doc_id 应被使用。"""
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    rid = await rag.add("x", doc_id="my-doc-1")
    assert rid == "my-doc-1"


@pytest.mark.asyncio
async def test_rag_memory_search_returns_empty_list():
    """stub 阶段 search 返回空 list。"""
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    results = await rag.search("query", k=5)
    assert results == []


@pytest.mark.asyncio
async def test_rag_memory_search_accepts_filter():
    """search 带 where_filter 参数不抛错。"""
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    results = await rag.search("q", k=3, where_filter={"type": "chapter"})
    assert results == []


@pytest.mark.asyncio
async def test_rag_memory_delete_is_noop():
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    await rag.delete("any-id")
    # 不抛错


@pytest.mark.asyncio
async def test_rag_memory_clear_is_noop():
    from src.core.memory.rag_memory import RagMemory

    rag = RagMemory(novel_id=1)
    await rag.clear()


@pytest.mark.asyncio
async def test_rag_memory_collection_parameter():
    """collection 参数不影响 stub 行为。"""
    from src.core.memory.rag_memory import RagMemory

    rag1 = RagMemory(novel_id=1, collection="chapters")
    rag2 = RagMemory(novel_id=1, collection="inspiration")
    rid1 = await rag1.add("a")
    rid2 = await rag2.add("b")
    # stub 阶段两个都返回 id（不冲突检查）
    assert rid1 != rid2


# ===== ConversationMemory（真实现）=====


def test_conversation_memory_starts_empty():
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1")
    assert len(mem) == 0
    assert mem.get_messages() == []


def test_conversation_memory_add_user_assistant():
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1")
    mem.add_user("hi")
    mem.add_assistant("hello!")
    msgs = mem.get_messages()
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "hi"}
    assert msgs[1] == {"role": "assistant", "content": "hello!"}


def test_conversation_memory_add_message_validates_role():
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1")
    with pytest.raises(ValueError, match="Invalid role"):
        mem.add_message("tool", "x")  # type: ignore[arg-type]


def test_conversation_memory_get_last_user_message():
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1")
    assert mem.get_last_user_message() is None

    mem.add_assistant("hi")
    assert mem.get_last_user_message() is None

    mem.add_user("how are you?")
    assert mem.get_last_user_message() == "how are you?"

    mem.add_assistant("fine")
    assert mem.get_last_user_message() == "how are you?"  # 还是上条 user


def test_conversation_memory_clear_keeps_system():
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1", max_turns=100)
    mem.add_system("你是修仙小说家")
    mem.add_user("开头怎么写？")
    mem.add_assistant("七月的青牛镇，烈日当空...")

    assert len(mem) == 3

    mem.clear()
    msgs = mem.get_messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"


def test_conversation_memory_truncate_keeps_system():
    """truncate 应保留 system + 最后 N 轮 user/assistant。"""
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1", max_turns=2)
    mem.add_system("system msg")
    # 加 5 轮 = 10 条
    for i in range(5):
        mem.add_user(f"u{i}")
        mem.add_assistant(f"a{i}")

    # max_turns=2 → 保留 2*2=4 条 user/assistant + system
    mem.truncate()
    msgs = mem.get_messages()
    assert len(msgs) == 5  # 1 system + 4 user/assistant
    assert msgs[0]["role"] == "system"
    # 保留的是后 2 轮：u3/a3/u4/a4
    assert msgs[1]["content"] == "u3"
    assert msgs[2]["content"] == "a3"
    assert msgs[3]["content"] == "u4"
    assert msgs[4]["content"] == "a4"


def test_conversation_memory_auto_truncate_on_add():
    """max_turns=2，超过 2 轮时自动 truncate。"""
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1", max_turns=2)
    # 3 轮对话
    mem.add_user("u0")
    mem.add_assistant("a0")
    mem.add_user("u1")
    mem.add_assistant("a1")
    mem.add_user("u2")  # 触发截断
    mem.add_assistant("a2")

    msgs = mem.get_messages()
    assert len(msgs) == 4  # 只剩 2 轮
    assert msgs[0] == {"role": "user", "content": "u1"}
    assert msgs[3] == {"role": "assistant", "content": "a2"}


def test_conversation_memory_rejects_invalid_max_turns():
    from src.core.memory.conversation_memory import ConversationMemory

    with pytest.raises(ValueError, match="max_turns"):
        ConversationMemory(session_id="s1", max_turns=0)
    with pytest.raises(ValueError, match="max_turns"):
        ConversationMemory(session_id="s1", max_turns=-1)


def test_conversation_memory_get_messages_returns_copy():
    """返回的是拷贝，外部修改不影响内部。"""
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1")
    mem.add_user("hi")
    msgs = mem.get_messages()
    msgs.append({"role": "user", "content": "modified"})
    # 内部不变
    assert len(mem) == 1


def test_conversation_memory_integration_with_llm_call():
    """模拟给 LLM 调用的场景：拿到 messages 列表传给 LLM。"""
    from src.core.memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(session_id="s1", max_turns=10)
    mem.add_user("继续写韩立下山")
    mem.add_assistant("韩立背起行囊，走出青牛镇...")
    mem.add_user("加点路途艰辛")

    msgs = mem.get_messages()
    # 模拟 LLM 输入格式：OpenAI 风格 [{"role": ..., "content": ...}]
    assert all("role" in m and "content" in m for m in msgs)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
