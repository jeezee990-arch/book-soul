"""聊天服务（项目 / 对话 / 消息 + 流式对话）。

对应需求
--------
「开设一个新的聊天界面，可以与云端模型聊天探讨想法，需要有多窗口以及项目管理模块
（进入聊天界面后从左侧弹出一个窗口栏，项目内可以新建对话，项目可以从素材库选择素材进行接入）」。

三层结构
--------
项目（:class:`ChatProject`）→ 对话（:class:`ChatConversation`）→ 消息（:class:`ChatMessage`）

素材接入
--------
项目里存 **inspiration id 列表**；每次发消息时把命中的素材内容拼进 system prompt。
素材被删了 id 自然失效，不用清理关联表。

流式协议
--------
- ``{"event": "user_message", "message": {...}}`` —— 用户消息已入库
- ``{"event": "thinking", "text": "..."}`` —— 推理模型思考中
- ``{"event": "delta", "text": "..."}`` —— 正文增量
- ``{"event": "done", "message": {...}, "model": "...", "elapsed_sec": 1.2}``
- ``{"event": "error", "message": "..."}``
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage as LLMChatMessage
from ..core.llm.base import describe_llm_error
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..models.chat import ChatConversation, ChatMessage, ChatProject
from ..models.inspiration import Inspiration

__all__ = ["ChatService", "ChatServiceError", "ChatNotFoundError"]

# 送给模型的最近历史消息条数（上下文太长会拖慢并挤爆 context window）
MAX_HISTORY_MESSAGES = 40
# 素材内容最多塞多少字进 system prompt
MAX_MATERIAL_CHARS = 3000
DEFAULT_SYSTEM_PROMPT = (
    "你是一位小说创作助手，正在与作者讨论创作想法。"
    "回答要简洁、有建设性，帮作者把模糊的想法梳理成可执行的剧情/人物/结构。"
)


class ChatServiceError(Exception):
    """聊天服务错误。"""


class ChatNotFoundError(ChatServiceError):
    """对象不存在。"""


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口。"""

    provider: str

    async def chat(
        self,
        # ⚠️ 必须用 LLMChatMessage（core.llm.base 那个）：本模块还 import 了
        #    ORM 的 ``ChatMessage``（models.chat），裸 ``ChatMessage`` 会被解析成
        #    那个 → 协议签名与真实客户端对不上（mypy 报 arg-type 不兼容）。
        messages: list[LLMChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any: ...


def _material_text(inspiration: Inspiration) -> str:
    """把一条素材渲染成一行可读文本。"""
    content = inspiration.content or {}
    parts: list[str] = []
    for key in ("title", "summary", "text", "content", "keywords", "tags"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}：{value.strip()}")
        elif isinstance(value, list) and value:
            parts.append(f"{key}：" + "、".join(str(x) for x in value))
    if not parts:
        try:
            parts.append(json.dumps(content, ensure_ascii=False)[:200])
        except (TypeError, ValueError):
            parts.append(str(content)[:200])
    return f"[{inspiration.type}] " + " | ".join(parts)


class ChatService:
    """聊天服务。"""

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("chat")
        return self._llm

    async def _release_llm(self, llm: _LLMClientLike, owns: bool) -> None:
        aclose = getattr(llm, "aclose", None)
        if owns and aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    # ===== 项目 =====

    async def list_projects(self) -> list[ChatProject]:
        """列出所有项目（按更新时间倒序 —— 最近用的排前面）。"""
        result = await self.session.execute(
            select(ChatProject).order_by(ChatProject.updated_at.desc(), ChatProject.id)
        )
        return list(result.scalars())

    async def get_project(self, project_id: int) -> ChatProject:
        """按 id 取项目；不存在抛 :class:`ChatNotFoundError`。"""
        project = await self.session.get(ChatProject, project_id)
        if project is None:
            raise ChatNotFoundError(f"Chat project {project_id} not found")
        return project

    async def create_project(self, data: Any) -> ChatProject:
        """新建项目。"""
        project = ChatProject(
            name=data.name.strip(),
            description=(data.description or "").strip() or None,
            materials=list(data.materials or []),
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update_project(self, project_id: int, data: Any) -> ChatProject:
        """更新项目（部分更新）。"""
        project = await self.get_project(project_id)
        if data.name is not None:
            project.name = data.name.strip()
        if data.description is not None:
            project.description = data.description.strip() or None
        if data.materials is not None:
            project.materials = list(data.materials)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete_project(self, project_id: int) -> None:
        """删除项目（级联删掉它的对话与消息）。幂等。"""
        project = await self.session.get(ChatProject, project_id)
        if project is None:
            return
        await self.session.delete(project)
        await self.session.commit()

    async def set_project_materials(
        self, project_id: int, inspiration_ids: list[int]
    ) -> ChatProject:
        """整体替换项目接入的素材列表。"""
        project = await self.get_project(project_id)
        # 去重 + 只保留真实存在的 id
        unique = list(dict.fromkeys(int(i) for i in inspiration_ids))
        valid: list[int] = []
        if unique:
            result = await self.session.execute(
                select(Inspiration.id).where(Inspiration.id.in_(unique))
            )
            valid = [int(i) for i in result.scalars()]
        project.materials = valid
        await self.session.commit()
        await self.session.refresh(project)
        return project

    # ===== 对话 =====

    async def list_conversations(self, project_id: int) -> list[ChatConversation]:
        """列出项目下的所有对话。"""
        result = await self.session.execute(
            select(ChatConversation)
            .where(ChatConversation.project_id == project_id)
            .order_by(ChatConversation.updated_at.desc(), ChatConversation.id)
        )
        return list(result.scalars())

    async def get_conversation(self, conversation_id: int) -> ChatConversation:
        """按 id 取对话；不存在抛 :class:`ChatNotFoundError`。"""
        conversation = await self.session.get(ChatConversation, conversation_id)
        if conversation is None:
            raise ChatNotFoundError(f"Chat conversation {conversation_id} not found")
        return conversation

    async def create_conversation(
        self, project_id: int, title: str = "新对话", model: str | None = None
    ) -> ChatConversation:
        """新建对话。"""
        await self.get_project(project_id)
        conversation = ChatConversation(
            project_id=project_id,
            title=(title or "新对话").strip()[:200] or "新对话",
            model=model,
        )
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def update_conversation(
        self, conversation_id: int, title: str | None = None, model: str | None = None
    ) -> ChatConversation:
        """更新对话（重命名 / 换模型）。"""
        conversation = await self.get_conversation(conversation_id)
        if title is not None:
            conversation.title = title.strip()[:200] or conversation.title
        if model is not None:
            conversation.model = model or None
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def delete_conversation(self, conversation_id: int) -> None:
        """删除对话（级联删消息）。幂等。"""
        conversation = await self.session.get(ChatConversation, conversation_id)
        if conversation is None:
            return
        await self.session.delete(conversation)
        await self.session.commit()

    # ===== 消息 =====

    async def list_messages(self, conversation_id: int, limit: int = 500) -> list[ChatMessage]:
        """按时间正序列出消息。"""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id)
            .limit(limit)
        )
        return list(result.scalars())

    async def _add_message(
        self, conversation_id: int, role: str, content: str, model: str | None = None
    ) -> ChatMessage:
        """写一条消息。"""
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    # ===== 对话（LLM） =====

    async def build_system_prompt(self, project: ChatProject) -> str:
        """拼 system prompt（含项目说明 + 接入的素材）。"""
        lines = [DEFAULT_SYSTEM_PROMPT]
        if project.name:
            lines.append(f"\n【当前项目】{project.name}")
        if project.description:
            lines.append(f"项目说明：{project.description}")
        materials = list(project.materials or [])
        if materials:
            result = await self.session.execute(
                select(Inspiration).where(Inspiration.id.in_(materials))
            )
            rows = list(result.scalars())
            if rows:
                lines.append("\n【已接入的素材】")
                for insp in rows:
                    lines.append(_material_text(insp))
        return "\n".join(lines)[: MAX_MATERIAL_CHARS + 1000]

    async def stream_chat(
        self,
        conversation_id: int,
        content: str,
        *,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式对话。

        流程：
        1. 用户消息入库（先存 —— 万一模型失败，用户的输入也不丢）
        2. 拼 messages（system + 历史 + 本轮）
        3. 流式调 LLM，边收边推 ``delta``
        4. 助手消息入库 → 推 ``done``
        """
        conversation = await self.get_conversation(conversation_id)
        project = await self.get_project(conversation.project_id)

        user_message = await self._add_message(conversation_id, "user", content, model=model)
        # 首条消息当标题（比"新对话"有用）
        if conversation.title == "新对话":
            conversation.title = content.strip()[:24] or "新对话"
            await self.session.commit()

        yield {"event": "user_message", "message": _message_dict(user_message)}

        history = await self.list_messages(conversation_id)
        history = history[-MAX_HISTORY_MESSAGES:]
        system_prompt = await self.build_system_prompt(project)
        messages = [LLMChatMessage("system", system_prompt)]
        for m in history:
            if m.role in ("user", "assistant") and m.content.strip():
                messages.append(LLMChatMessage(m.role, m.content))

        llm = self._get_llm()
        owns_client = self._llm_override is None
        used_model = model or getattr(llm, "model", "") or ""
        splitter = ThinkSplitter()
        full_text = ""
        t0 = time.monotonic()
        saved = False
        try:
            stream = await llm.chat(messages, temperature=0.7, stream=True)
            async for delta in stream:
                if not delta:
                    continue
                for kind, text in splitter.feed(delta):
                    if kind == KIND_THINK:
                        yield {"event": "thinking", "text": text}
                        continue
                    full_text += text
                    yield {"event": "delta", "text": text}

            # 流正常结束 → 入库完整回复（**必须放在 try 里面**：
            # finally 里还有一个"中断时存半截"的兜底，两处都存会存成两条）
            if not full_text.strip():
                yield {"event": "error", "message": "模型没有返回内容"}
                return
            assistant = await self._add_message(
                conversation_id, "assistant", full_text, model=used_model
            )
            saved = True
            yield {
                "event": "done",
                "message": _message_dict(assistant),
                "model": used_model,
                "provider": str(getattr(llm, "provider", "") or ""),
                "elapsed_sec": round(time.monotonic() - t0, 2),
            }
        except Exception as e:  # noqa: BLE001
            logger.error("chat stream failed: {}", describe_llm_error(e))
            yield {"event": "error", "message": describe_llm_error(e)}
            return
        finally:
            # 客户端中断（用户点「停止」/ 关闭窗口）时，async generator 会被
            # close → 已经吐出来的半截也要存下来，不能凭空消失。
            #
            # ⚠️ saved 为 True 说明完整回复已经存过了 —— 这里**不能再存一次**
            #    （否则同一条回复会入库两条，历史里出现重复）。
            if not saved and full_text.strip():
                try:
                    await self._add_message(
                        conversation_id, "assistant", full_text, model=used_model
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("保存半截回复失败: {}", describe_llm_error(e))
            if owns_client:
                await self._release_llm(llm, owns=True)


def _message_dict(message: ChatMessage) -> dict[str, Any]:
    """消息 → 可 JSON 序列化的 dict。"""
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "model": message.model,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }
