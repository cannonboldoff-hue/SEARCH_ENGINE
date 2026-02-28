"""
ElevenLabs Conversational AI integration.

- POST /convai/signed-url: authenticated; returns signed WebSocket URL
- POST /convai/v1/chat/completions: OpenAI-compatible; called by ElevenLabs (custom LLM)
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlparse, parse_qs

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core import decode_access_token
from src.db.session import async_session
from src.db.models import Person
from src.dependencies import get_db
from sqlalchemy import select
from src.services.convai import (
    create_session,
    get_session,
    convai_chat_turn,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/convai", tags=["convai"])


async def _get_user_from_token(token: str | None) -> Person | None:
    """Decode JWT and load user. Returns None if invalid."""
    if not token or not token.strip():
        return None
    user_id = decode_access_token(token.strip())
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(Person).where(Person.id == user_id))
        return result.scalar_one_or_none()


@router.post("/signed-url")
async def get_signed_url(request: Request):
    """
    Get a signed WebSocket URL for ElevenLabs Conversational AI.
    Requires Authorization: Bearer <token>.
    Creates a session and returns the URL. The frontend uses this to connect.
    """
    settings = get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_agent_id:
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs Conversational AI is not configured.",
        )
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
        )
    token = auth[7:].strip()
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    url = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
    params = {
        "agent_id": settings.elevenlabs_agent_id,
        "include_conversation_id": "true",
    }
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("ElevenLabs get-signed-url failed %s: %s", e.response.status_code, e.response.text[:500])
        raise HTTPException(status_code=503, detail="Could not get voice session. Please try again.")
    except Exception as e:
        logger.exception("ElevenLabs get-signed-url error: %s", e)
        raise HTTPException(status_code=503, detail="Voice service unavailable.")

    signed_url = data.get("signed_url")
    conversation_id = data.get("conversation_id")
    if not signed_url:
        raise HTTPException(status_code=503, detail="Invalid response from voice service.")
    # conversation_id may be in response or encoded in the signed URL
    if not conversation_id:
        parsed = urlparse(signed_url)
        params = parse_qs(parsed.query)
        conversation_id = (params.get("conversation_id") or [None])[0]

    if conversation_id:
        create_session(str(conversation_id), user.id)

    return {
        "signed_url": signed_url,
        "conversation_id": conversation_id,
    }


def _sse_chunk(content: str, delta: bool = True) -> str:
    """Format one SSE chunk (OpenAI streaming)."""
    obj = {
        "id": "convai-1",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": content} if delta else {}, "finish_reason": None}],
    }
    return f"data: {json.dumps(obj)}\n\n"


async def _stream_response(text: str):
    """Stream text as OpenAI SSE chunks (async generator)."""
    if text:
        yield _sse_chunk(text, delta=True)
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint for ElevenLabs custom LLM.
    ElevenLabs calls this with conversation messages. We run our clarify pipeline
    and stream the assistant reply.

    Conversation identification: ElevenLabs may pass X-Conversation-Id or
    X-ElevenLabs-Conversation-Id. If not found, we cannot associate the request
    with a user session.
    """
    conversation_id = (
        request.headers.get("X-Conversation-Id")
        or request.headers.get("X-ElevenLabs-Conversation-Id")
        or request.headers.get("x-conversation-id")
    )
    if not conversation_id or not conversation_id.strip():
        logger.warning("chat/completions: no conversation_id header")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Conversation-Id header",
        )

    session_data = get_session(conversation_id.strip())
    if not session_data:
        logger.warning("chat/completions: unknown conversation_id=%s", conversation_id)
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please start a new voice session.",
        )
    user_id, state = session_data

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = body.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages array required")
    stream = body.get("stream", True)

    async with async_session() as db:
        try:
            reply = await convai_chat_turn(
                conversation_id=conversation_id.strip(),
                user_id=user_id,
                messages=messages,
                db=db,
                state=state,
            )
        except Exception as e:
            logger.exception("convai_chat_turn failed: %s", e)
            reply = "I'm sorry, something went wrong. Could you try again?"

    if stream:
        return StreamingResponse(
            _stream_response(reply),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return {
        "id": "convai-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
    }
