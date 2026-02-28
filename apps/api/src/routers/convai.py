"""
Vapi AI integration for conversational voice.

- POST /convai/call: Proxy for Vapi web calls; creates call with custom LLM including user context
- POST /convai/v1/chat/completions: OpenAI-compatible; called by Vapi (custom LLM)
"""

from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core import decode_access_token
from src.db.session import async_session
from src.db.models import Person
from sqlalchemy import select
from src.services.convai import (
    create_session,
    get_session,
    convai_chat_turn,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/convai", tags=["convai"])
DEBUG_LOG_PATH = r"c:\Users\Lenovo\Desktop\Search_Engine\.cursor\debug.log"


def _debug_log(
    *,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "id": f"log_{int(time.time() * 1000)}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
    }
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        # Never break request flow because of debug logging.
        pass
    logger.info("convai_debug %s %s %s", hypothesis_id, message, data or {})


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


@router.api_route("/call/web", methods=["POST", "OPTIONS"])
@router.api_route("/call", methods=["POST", "OPTIONS"])
async def vapi_call_proxy(request: Request):
    """
    Proxy for Vapi web calls. Requires Authorization: Bearer <token>.
    Creates a call with a transient assistant that uses our custom LLM (with user_id).
    The frontend uses the Vapi Web SDK with this URL as the proxy base.
    """
    if request.method == "OPTIONS":
        return Response(status_code=204)

    settings = get_settings()
    if not settings.vapi_api_key or not settings.vapi_callback_base_url:
        raise HTTPException(
            status_code=503,
            detail="Vapi voice is not configured.",
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

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Build transient assistant with custom LLM URL including user_id.
    # Use base path without /chat/completions so Vapi appends it before the query string.
    # (Vapi appends "/chat/completions" to the URL; passing the full path caused it to
    # end up inside user_id, e.g. "uuid/chat/completions".)
    llm_base = f"{settings.vapi_callback_base_url.rstrip('/')}/convai/v1"
    llm_url_with_user = f"{llm_base}?{urlencode({'user_id': str(user.id)})}"
    # region agent log
    _debug_log(
        hypothesis_id="H1",
        location="convai.py:vapi_call_proxy",
        message="Built custom LLM URL for Vapi assistant",
        data={"llm_url": llm_url_with_user, "user_id": str(user.id)},
    )
    # endregion

    assistant = {
        "firstMessage": "What's one experience you'd like to add? Tell me in your own words.",
        "model": {
            "provider": "custom-llm",
            "url": llm_url_with_user,
            "model": "gpt-4o",
            "temperature": 0.7,
        },
        "voice": {
            "provider": settings.vapi_voice_provider,
            "voiceId": settings.vapi_voice_id,
        },
        "transcriber": {
            "provider": settings.vapi_transcriber_provider,
            "model": settings.vapi_transcriber_model,
            "language": "en",
        },
    }

    # Merge with any client overrides, but our assistant takes precedence
    payload = {**body, "assistant": assistant}

    # Forward to Vapi - use same path as request (call or call/web)
    vapi_path = "/call/web" if "/call/web" in str(request.url.path) else "/call"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.vapi.ai{vapi_path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.vapi_api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Vapi call create failed %s: %s", e.response.status_code, e.response.text[:500])
        raise HTTPException(status_code=503, detail="Could not start voice session. Please try again.")
    except Exception as e:
        logger.exception("Vapi call create error: %s", e)
        raise HTTPException(status_code=503, detail="Voice service unavailable.")

    # Session key for lookup when Vapi calls our custom LLM with ?user_id=X
    create_session(str(user.id), user.id)

    return data


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
    OpenAI-compatible chat completions endpoint for Vapi custom LLM.
    Vapi calls this with conversation messages. We run our clarify pipeline
    and stream the assistant reply.

    Session identification: Vapi passes user_id in the URL query when we use
    a per-call custom LLM URL. Also supports legacy X-Conversation-Id headers.
    """
    # Session identification: Vapi passes user_id in query; legacy ElevenLabs used conversation_id
    conversation_id = request.query_params.get("user_id")
    # region agent log
    _debug_log(
        hypothesis_id="H2",
        location="convai.py:chat_completions:entry",
        message="Incoming convai completion request",
        data={
            "path": str(request.url.path),
            "query": str(request.url.query),
            "raw_user_id_query": conversation_id,
        },
    )
    # endregion
    # Workaround: Vapi appends "/chat/completions" to the URL string, which can end up in
    # the query value. Strip that suffix if present (e.g. "uuid/chat/completions" -> "uuid").
    if conversation_id and conversation_id.endswith("/chat/completions"):
        # region agent log
        _debug_log(
            hypothesis_id="H3",
            location="convai.py:chat_completions:strip_suffix",
            message="Detected and stripping '/chat/completions' suffix from user_id query",
            data={"before": conversation_id},
        )
        # endregion
        conversation_id = conversation_id[: -len("/chat/completions")].rstrip("/")
        # region agent log
        _debug_log(
            hypothesis_id="H3",
            location="convai.py:chat_completions:strip_suffix_after",
            message="Suffix stripped from user_id query",
            data={"after": conversation_id},
        )
        # endregion
    if not conversation_id or not conversation_id.strip():
        conversation_id = (
            request.headers.get("X-Conversation-Id")
            or request.headers.get("X-ElevenLabs-Conversation-Id")
            or request.headers.get("x-conversation-id")
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not conversation_id or not conversation_id.strip():
        conversation_id = (
            body.get("conversation_id")
            or body.get("conversationId")
            or (body.get("metadata") or {}).get("conversation_id")
            or (body.get("metadata") or {}).get("conversationId")
        )
        if isinstance(conversation_id, str) and conversation_id.strip():
            pass
        else:
            conversation_id = None

    if not conversation_id or not conversation_id.strip():
        x_headers = {k: v for k, v in request.headers.items() if k.lower().startswith("x-")}
        # region agent log
        _debug_log(
            hypothesis_id="H4",
            location="convai.py:chat_completions:missing_context",
            message="Missing conversation context before rejection",
            data={
                "x_header_keys": list(x_headers.keys()),
                "body_keys": list(body.keys()) if isinstance(body, dict) else [],
            },
        )
        # endregion
        logger.warning(
            "chat/completions: no conversation_id/user_id (x-* headers=%s, body_keys=%s)",
            x_headers,
            list(body.keys()) if isinstance(body, dict) else [],
        )
        raise HTTPException(
            status_code=400,
            detail="Missing conversation context. Ensure Vapi assistant uses custom LLM URL with user_id.",
        )

    # region agent log
    _debug_log(
        hypothesis_id="H5",
        location="convai.py:chat_completions:get_session",
        message="Looking up convai session",
        data={"conversation_id": conversation_id.strip()},
    )
    # endregion
    session_data = get_session(conversation_id.strip())
    if not session_data:
        # region agent log
        _debug_log(
            hypothesis_id="H5",
            location="convai.py:chat_completions:session_not_found",
            message="Convai session lookup failed",
            data={"conversation_id": conversation_id},
        )
        # endregion
        logger.warning("chat/completions: unknown conversation_id=%s", conversation_id)
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please start a new voice session.",
        )
    user_id, state = session_data

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
