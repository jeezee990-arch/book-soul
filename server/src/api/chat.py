"""聊天 REST 端点（项目 / 对话 / 消息 + 流式对话）。

端点：
- GET    /chat/projects                                  列出项目
- POST   /chat/projects                                  新建项目
- GET    /chat/projects/{pid}                            项目详情
- PATCH  /chat/projects/{pid}                            更新项目
- DELETE /chat/projects/{pid}                            删除项目（级联）
- PUT    /chat/projects/{pid}/materials                  接入素材（整体替换）
- GET    /chat/projects/{pid}/conversations              项目下的对话
- POST   /chat/projects/{pid}/conversations              新建对话
- PATCH  /chat/conversations/{cid}                       重命名 / 换模型
- DELETE /chat/conversations/{cid}                       删除对话
- GET    /chat/conversations/{cid}/messages              消息历史
- POST   /chat/conversations/{cid}/messages              发消息（非流式）
- POST   /chat/conversations/{cid}/messages/stream       发消息（ndjson 流式）

错误映射：
- ChatNotFoundError → 404
- ChatServiceError → 422
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.chat import (
    ChatConversationCreate,
    ChatConversationRead,
    ChatConversationUpdate,
    ChatMessageRead,
    ChatProjectCreate,
    ChatProjectRead,
    ChatProjectUpdate,
    ChatSendRequest,
)
from ..services.chat_service import ChatNotFoundError, ChatService
from ._stream_helpers import ndjson_line, ndjson_response

router = APIRouter(prefix="/chat", tags=["chat"])


def get_service(session: AsyncSession = Depends(get_db)) -> ChatService:
    """依赖注入：拿一个 ChatService。"""
    return ChatService(session)


class MaterialsRequest(BaseModel):
    """整体替换项目接入的素材。"""

    inspiration_ids: list[int] = Field(default_factory=list, max_length=100)


# ===== 项目 =====


@router.get("/projects", response_model=list[ChatProjectRead], summary="列出聊天项目")
async def list_projects(service: ChatService = Depends(get_service)) -> list[ChatProjectRead]:
    projects = await service.list_projects()
    return [ChatProjectRead.model_validate(p) for p in projects]


@router.post(
    "/projects",
    response_model=ChatProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="新建聊天项目",
)
async def create_project(
    payload: ChatProjectCreate, service: ChatService = Depends(get_service)
) -> ChatProjectRead:
    project = await service.create_project(payload)
    return ChatProjectRead.model_validate(project)


@router.get("/projects/{project_id}", response_model=ChatProjectRead, summary="项目详情")
async def get_project(
    project_id: int, service: ChatService = Depends(get_service)
) -> ChatProjectRead:
    try:
        project = await service.get_project(project_id)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChatProjectRead.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ChatProjectRead, summary="更新聊天项目")
async def update_project(
    project_id: int,
    payload: ChatProjectUpdate,
    service: ChatService = Depends(get_service),
) -> ChatProjectRead:
    try:
        project = await service.update_project(project_id, payload)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChatProjectRead.model_validate(project)


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除聊天项目（级联删对话与消息）",
)
async def delete_project(project_id: int, service: ChatService = Depends(get_service)) -> None:
    await service.delete_project(project_id)


@router.put(
    "/projects/{project_id}/materials",
    response_model=ChatProjectRead,
    summary="接入素材（整体替换 inspiration id 列表）",
)
async def set_materials(
    project_id: int,
    payload: MaterialsRequest,
    service: ChatService = Depends(get_service),
) -> ChatProjectRead:
    try:
        project = await service.set_project_materials(project_id, payload.inspiration_ids)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChatProjectRead.model_validate(project)


# ===== 对话 =====


@router.get(
    "/projects/{project_id}/conversations",
    response_model=list[ChatConversationRead],
    summary="列出项目下的对话",
)
async def list_conversations(
    project_id: int, service: ChatService = Depends(get_service)
) -> list[ChatConversationRead]:
    try:
        rows = await service.list_conversations(project_id)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [ChatConversationRead.model_validate(c) for c in rows]


@router.post(
    "/projects/{project_id}/conversations",
    response_model=ChatConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="新建对话",
)
async def create_conversation(
    project_id: int,
    payload: ChatConversationCreate,
    service: ChatService = Depends(get_service),
) -> ChatConversationRead:
    try:
        conversation = await service.create_conversation(
            project_id, title=payload.title, model=payload.model
        )
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChatConversationRead.model_validate(conversation)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ChatConversationRead,
    summary="重命名对话 / 换模型",
)
async def update_conversation(
    conversation_id: int,
    payload: ChatConversationUpdate,
    service: ChatService = Depends(get_service),
) -> ChatConversationRead:
    try:
        conversation = await service.update_conversation(
            conversation_id, title=payload.title, model=payload.model
        )
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChatConversationRead.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除对话（级联删消息）",
)
async def delete_conversation(
    conversation_id: int, service: ChatService = Depends(get_service)
) -> None:
    await service.delete_conversation(conversation_id)


# ===== 消息 =====


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageRead],
    summary="消息历史",
)
async def list_messages(
    conversation_id: int, service: ChatService = Depends(get_service)
) -> list[ChatMessageRead]:
    try:
        rows = await service.list_messages(conversation_id)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [ChatMessageRead.model_validate(m) for m in rows]


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    summary="发消息并流式接收回复（ndjson）",
)
async def send_message_stream(
    conversation_id: int,
    payload: ChatSendRequest,
    service: ChatService = Depends(get_service),
):
    """流式聊天端点。

    协议：``user_message`` / ``thinking`` / ``delta`` / ``done`` / ``error``。

    ⚠️ 前置校验放在**开流之前**（对话是否还存在）。
    否则：对话被删掉时异常在 generator 里抛 → 客户端收到一段被截断的 200
    响应 → 既没有 error 帧也没有 done 帧 → 前端界面永远转圈，
    用户刚打的字也随流一起丢了（AGENTS.md §4.10）。
    """
    try:
        await service.get_conversation(conversation_id)
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    async def gen():
        async for event in service.stream_chat(
            conversation_id, payload.content, model=payload.model
        ):
            yield ndjson_line(event)

    return ndjson_response(gen())
