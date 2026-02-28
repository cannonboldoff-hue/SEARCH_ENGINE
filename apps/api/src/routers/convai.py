"""
Vapi AI integration for conversational voice.

- POST /convai/call: Proxy for Vapi web calls; creates call with custom LLM including user context
- POST /convai/v1/chat/completions: OpenAI-compatible; called by Vapi (custom LLM)
- POST /convai/v1: Compatibility alias (Vapi appends /chat/completions to the URL, which ends up
  in the query string when user_id is a query param; this route catches that shape)
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse

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

    # Session is stored in this process. Vapi (cloud) must call back to THIS server.
    # If request hits localhost but callback points to production, session won't be found (404).
    request_host = urlparse(str(request.base_url)).hostname or ""
    callback_host = urlparse(settings.vapi_callback_base_url or "").hostname or ""
    is_local_request = request_host in ("127.0.0.1", "localhost", "")
    is_callback_remote = callback_host and callback_host not in ("127.0.0.1", "localhost")
    if is_local_request and is_callback_remote:
        logger.warning(
            "Voice call rejected: local request (host=%s) but callback points to %s",
            request_host,
            callback_host,
        )
        raise HTTPException(
            status_code=503,
            detail="Voice requires the callback URL to reach this server. You're running locally but VAPI_CALLBACK_BASE_URL points to another host. For local testing, set VAPI_CALLBACK_BASE_URL to a tunnel (e.g. ngrok) that forwards to this API.",
        )

    # Build transient assistant with custom LLM URL including user_id.
    # We pass only the base path (/convai/v1) so Vapi appends /chat/completions
    # before the query string. If the full path were included, Vapi would produce
    # /convai/v1/chat/completions?user_id=uuid/chat/completions (suffix in value).
    llm_base = f"{settings.vapi_callback_base_url.rstrip('/')}/convai/v1"
    llm_url_with_user = f"{llm_base}?{urlencode({'user_id': str(user.id)})}"

    assistant = {
        "firstMessage": "What would you like to share today? Please tell me. When you're done, just say thank you.",
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
        # Allow long storytelling with natural pauses (e.g. 5s before assuming end of turn)
        "silenceTimeoutSeconds": 300,
        "startSpeakingPlan": {
            "waitSeconds": 1.0,
            "transcriptionEndpointingPlan": {
                "onPunctuationSeconds": 0.5,
                # 6s before first "thank you" so long first answer isn't cut off; custom rule ends on "thank you"
                "onNoPunctuationSeconds": 6.0,
                "onNumberSeconds": 0.8,
            },
            # First turn: listen until user says "thank you"; after that, normal endpointing
            "customEndpointingRules": [
                {
                    "type": "user",
                    "regex": "(?i)(thank you|thanks|thank u|that's all|thats all)",
                    "timeoutSeconds": 0.5,
                },
            ],
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


@router.post("/v1")
@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint for Vapi custom LLM.
    Vapi calls this with conversation messages. We run our clarify pipeline
    and stream the assistant reply.

    Session identification: Vapi passes user_id in the URL query when we use
    a per-call custom LLM URL. Also supports legacy X-Conversation-Id headers.

    Route /v1 is a compatibility alias: Vapi appends /chat/completions to the
    custom LLM URL string, which—when user_id is already a query param—produces
    POST /convai/v1?user_id=<uuid>/chat/completions (path stays /convai/v1,
    suffix lands inside the query value). Both routes share this handler;
    the suffix-stripping logic below cleans the user_id value when needed.
    """
    conversation_id = request.query_params.get("user_id")
    # Vapi appends "/chat/completions" to the URL string, which can end up in
    # the query value when user_id is already a query param.
    # Strip that suffix if present (e.g. "uuid/chat/completions" -> "uuid").
    if conversation_id and conversation_id.endswith("/chat/completions"):
        conversation_id = conversation_id[: -len("/chat/completions")].rstrip("/")
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
        logger.warning(
            "chat/completions: no conversation_id/user_id (x-* headers=%s, body_keys=%s)",
            x_headers,
            list(body.keys()) if isinstance(body, dict) else [],
        )
        raise HTTPException(
            status_code=400,
            detail="Missing conversation context. Ensure Vapi assistant uses custom LLM URL with user_id.",
        )

    session_data = get_session(conversation_id.strip())
    if not session_data:
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
