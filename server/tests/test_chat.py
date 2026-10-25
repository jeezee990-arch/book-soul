"""聊天模块单元测试（2026-10-25 新增）。

覆盖：
- 项目 / 对话 / 消息的 CRUD
- 素材接入（只保留真实存在的 inspiration id）
- 流式对话：user_message → delta → done，消息都入库
- 端点错误映射（不存在 → 404）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.schemas.chat import (
    ChatConversationCreate,
    ChatProjectCreate,
    ChatProjectUpdate,
)
from src.services.chat_service import ChatNotFoundError, ChatService


class _FakeStreamLLM:
    """按片段吐出内容的假 LLM。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.calls: list[list[ChatMessage]] = []

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        self.calls.append(messages)
        if not stream:
            return ChatResponse(content="".join(self.chunks), model=self.model)

        async def _gen():
            for chunk in self.chunks:
                yield chunk

        return _gen()


async def _seed_inspiration(session: Any, content: dict[str, Any]) -> int:
    """建一条素材，返回 id。"""
    from src.models.inspiration import Inspiration

    insp = Inspiration(type="note", content=content, tags=[])
    session.add(insp)
    await session.commit()
    await session.refresh(insp)
    return insp.id


# ===== 项目 =====


@pytest.mark.asyncio
async def test_project_crud(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        service = ChatService(session)
        project = await service.create_project(
            ChatProjectCreate(name="新书构思", description="关于一个废柴的故事")
        )
        assert project.id > 0
        assert project.name == "新书构思"

        updated = await service.update_project(project.id, ChatProjectUpdate(name="改个名"))
        assert updated.name == "改个名"

        listed = await service.list_projects()
        assert any(p.id == project.id for p in listed)

        await service.delete_project(project.id)
        with pytest.raises(ChatNotFoundError):
            await service.get_project(project.id)


@pytest.mark.asyncio
async def test_set_materials_keeps_only_existing_ids(db_initialized: Path) -> None:
    """只保留真实存在的 inspiration id（不存在的丢掉）。"""
    from src.db import SessionLocal

    async with SessionLocal() as session:
        real_id = await _seed_inspiration(session, {"summary": "一个想法"})

    async with SessionLocal() as session:
        service = ChatService(session)
        project = await service.create_project(ChatProjectCreate(name="素材项目"))
        updated = await service.set_project_materials(project.id, [real_id, 999999, real_id])
        assert updated.materials == [real_id]


@pytest.mark.asyncio
async def test_system_prompt_contains_materials(db_initialized: Path) -> None:
    """接入的素材要出现在 system prompt 里（否则模型不知道素材内容）。"""
    from src.db import SessionLocal

    async with SessionLocal() as session:
        insp_id = await _seed_inspiration(
            session, {"summary": "主角其实是外星人", "title": "核心设定"}
        )

    async with SessionLocal() as session:
        service = ChatService(session)
        project = await service.create_project(
            ChatProjectCreate(name="设定讨论", materials=[insp_id])
        )
        prompt = await service.build_system_prompt(project)
    assert "核心设定" in prompt
    assert "主角其实是外星人" in prompt
    assert "设定讨论" in prompt


# ===== 对话与消息 =====


@pytest.mark.asyncio
async def test_conversation_crud(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        service = ChatService(session)
        project = await service.create_project(ChatProjectCreate(name="项目"))
        conversation = await service.create_conversation(project.id, title="主线")
        assert conversation.project_id == project.id

        renamed = await service.update_conversation(conversation.id, title="支线")
        assert renamed.title == "支线"

        listed = await service.list_conversations(project.id)
        assert len(listed) == 1

        await service.delete_conversation(conversation.id)
        with pytest.raises(ChatNotFoundError):
            await service.get_conversation(conversation.id)


@pytest.mark.asyncio
async def test_stream_chat_saves_messages(db_initialized: Path) -> None:
    """流式对话：用户消息 + 助手消息都入库，并按顺序推事件。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(["你好", "，", "我是助手"])

    async with SessionLocal() as session:
        service = ChatService(session, llm_client=llm)
        project = await service.create_project(ChatProjectCreate(name="项目"))
        conversation = await service.create_conversation(project.id)
        events = [ev async for ev in service.stream_chat(conversation.id, "帮我看看这个设定")]

    kinds = [e["event"] for e in events]
    assert kinds[0] == "user_message"
    assert "delta" in kinds
    assert kinds[-1] == "done"
    assert "".join(e["text"] for e in events if e["event"] == "delta") == "你好，我是助手"

    async with SessionLocal() as session:
        messages = await ChatService(session).list_messages(conversation.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "帮我看看这个设定"
    assert messages[1].content == "你好，我是助手"


@pytest.mark.asyncio
async def test_stream_chat_partial_saved_once_on_client_abort(db_initialized: Path) -> None:
    """用户点「停止」→ 半截回复要入库，而且**只入库一条**。

    ⚠️ 2026-10-25 巡检踩过的坑：完整回复的保存原本放在 try 块**外面**，
    finally 里的"中断存半截"兜底又存了一次 → 同一条回复入库两条，
    历史里出现重复。完整保存必须挪进 try 块并置 ``saved = True``。
    """
    from src.db import SessionLocal

    llm = _FakeStreamLLM(["第一段", "第二段"])
    async with SessionLocal() as session:
        service = ChatService(session, llm_client=llm)
        project = await service.create_project(ChatProjectCreate(name="项目"))
        conversation = await service.create_conversation(project.id)

        stream = service.stream_chat(conversation.id, "你好")
        async for ev in stream:
            if ev.get("event") == "delta":
                break  # 模拟用户点「停止」→ 中断消费
        await stream.aclose()

        messages = await service.list_messages(conversation.id)

    assistants = [m for m in messages if m.role == "assistant"]
    assert len(assistants) == 1, "半截回复只应入库一条"
    assert "第一段" in assistants[0].content


@pytest.mark.asyncio
async def test_stream_chat_sets_title_from_first_message(db_initialized: Path) -> None:
    """首条消息当对话标题（比"新对话"有用）。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(["好的"])
    async with SessionLocal() as session:
        service = ChatService(session, llm_client=llm)
        project = await service.create_project(ChatProjectCreate(name="项目"))
        conversation = await service.create_conversation(project.id)
        async for _ in service.stream_chat(conversation.id, "讨论一下主角动机"):
            pass

    async with SessionLocal() as session:
        updated = await ChatService(session).get_conversation(conversation.id)
    assert updated.title == "讨论一下主角动机"


@pytest.mark.asyncio
async def test_stream_chat_sends_history(db_initialized: Path) -> None:
    """第二轮对话要带上历史（system + 之前的消息）。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(["回答"])
    async with SessionLocal() as session:
        service = ChatService(session, llm_client=llm)
        project = await service.create_project(ChatProjectCreate(name="项目"))
        conversation = await service.create_conversation(project.id)
        async for _ in service.stream_chat(conversation.id, "第一句"):
            pass
        async for _ in service.stream_chat(conversation.id, "第二句"):
            pass

    # 第二次调用：system + user1 + assistant1 + user2
    last_call = llm.calls[-1]
    roles = [m.role for m in last_call]
    assert roles[0] == "system"
    assert roles.count("user") == 2
    assert roles.count("assistant") == 1


# ===== 端点 =====


@pytest.mark.asyncio
async def test_chat_api_project_flow(db_initialized: Path) -> None:
    """端点：建项目 → 建对话 → 发消息 → 读历史。"""
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        r = client.post("/chat/projects", json={"name": "端点项目"})
        assert r.status_code == 201
        project_id = r.json()["id"]

        r = client.post(f"/chat/projects/{project_id}/conversations", json={"title": "主线"})
        assert r.status_code == 201
        conversation_id = r.json()["id"]

        r = client.get(f"/chat/projects/{project_id}/conversations")
        assert r.status_code == 200
        assert len(r.json()) == 1

        r = client.get(f"/chat/conversations/{conversation_id}/messages")
        assert r.status_code == 200
        assert r.json() == []


def test_chat_api_missing_project_returns_404(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        r = client.get("/chat/projects/999999")
    assert r.status_code == 404


def test_chat_stream_api_missing_conversation_returns_404(db_initialized: Path) -> None:
    """对话不存在 → **开流之前**就 404。

    ⚠️ 2026-10-25 巡检：原来没有前置校验，对话被删掉时异常在 generator
    里抛 → 客户端收到一段被截断的 200 响应 → 既没 error 帧也没 done 帧
    → 前端界面永远转圈，用户刚打的字也丢了（AGENTS.md §4.10）。
    """
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        r = client.post("/chat/conversations/999999/messages/stream", json={"content": "你好"})
    assert r.status_code == 404


def test_chat_conversation_schema_defaults() -> None:
    payload = ChatConversationCreate()
    assert payload.title == "新对话"
    assert payload.model is None
