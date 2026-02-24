import logging
import asyncio
import json
import base64
import io
import wave
from datetime import date
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK

logger = logging.getLogger(__name__)

from src.db.models import Person, ExperienceCard, ExperienceCardChild
from src.db.session import async_session
from src.dependencies import (
    get_current_user,
    get_db,
    get_experience_card_or_404,
    get_experience_card_child_or_404,
)
from src.schemas import (
    RawExperienceCreate,
    RawExperienceResponse,
    RewriteTextResponse,
    TranslateTextResponse,
    TextToSpeechRequest,
    TextToSpeechResponse,
    DraftSetV1Response,
    DetectExperiencesResponse,
    DraftSingleRequest,
    FillFromTextRequest,
    FillFromTextResponse,
    ClarifyExperienceRequest,
    ClarifyExperienceResponse,
    CardFamilyV1Response,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
    ExperienceCardChildPatch,
    ExperienceCardChildResponse,
    FinalizeExperienceCardRequest,
)
from src.core import decode_access_token
from src.core.config import get_settings
from src.providers import (
    ChatServiceError,
    ChatRateLimitError,
    EmbeddingServiceError,
    SpeechServiceError,
    SpeechConfigError,
    TranslationServiceError,
    TranslationConfigError,
    get_speech_provider,
    get_translation_provider,
)
from src.serializers import experience_card_to_response, experience_card_child_to_response
from src.services.experience import (
    experience_card_service,
    apply_card_patch,
    apply_child_patch,
    embed_experience_cards,
    rewrite_raw_text,
    run_draft_v1_single,
    fill_missing_fields_from_text,
    clarify_experience_interactive,
    detect_experiences,
    DEFAULT_MAX_PARENT_CLARIFY,
    DEFAULT_MAX_CHILD_CLARIFY,
    PipelineError,
)

router = APIRouter(tags=["builder"])


async def _reembed_cards_after_update(
    db: AsyncSession,
    *,
    parents: list[ExperienceCard] | None = None,
    children: list[ExperienceCardChild] | None = None,
    context: str = "update",
) -> None:
    """
    Re-run embedding for the given cards after a content update (patch / fill / clarify).
    On failure, logs and raises HTTP 503.
    """
    parents = parents or []
    children = children or []
    if not parents and not children:
        return
    try:
        await embed_experience_cards(db, parents, children)
    except PipelineError as e:
        logger.warning("Re-embed after %s failed: %s", context, e)
        raise HTTPException(status_code=503, detail=str(e)) from e


def _is_wav_bytes(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _pcm16le_to_wav_bytes(pcm_data: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_writer:
        wav_writer.setnchannels(1)
        wav_writer.setsampwidth(2)
        wav_writer.setframerate(sample_rate)
        wav_writer.writeframes(pcm_data)
    return buf.getvalue()


def _normalize_audio_chunk_to_wav_b64(audio_b64: str, sample_rate: int) -> str | None:
    """
    Sarvam WS currently accepts audio.encoding='audio/wav'.
    Frontend sends PCM16LE chunk bytes, so wrap PCM chunks with a WAV header.
    """
    try:
        raw = base64.b64decode(audio_b64, validate=True)
    except Exception:
        logger.warning("Builder transcribe received invalid base64 audio chunk")
        return None

    if _is_wav_bytes(raw):
        return audio_b64

    try:
        wav_bytes = _pcm16le_to_wav_bytes(raw, sample_rate)
    except Exception:
        logger.exception("Builder transcribe failed to normalize PCM chunk to WAV")
        return None
    return base64.b64encode(wav_bytes).decode("ascii")


@router.post("/experiences/raw", response_model=RawExperienceResponse)
async def create_raw_experience(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await experience_card_service.create_raw(db, current_user.id, body)
    return RawExperienceResponse(id=raw.id, raw_text=raw.raw_text, created_at=raw.created_at)


@router.post("/experiences/rewrite", response_model=RewriteTextResponse)
async def rewrite_experience_text(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
):
    """Rewrite messy input into clear English for easier extraction. No persistence."""
    try:
        rewritten = await rewrite_raw_text(body.raw_text)
        return RewriteTextResponse(rewritten_text=rewritten)
    except ChatRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ChatServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/experiences/translate", response_model=TranslateTextResponse)
async def translate_experience_text(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
):
    """Translate multilingual input into English text using Sarvam Translate."""
    try:
        translator = get_translation_provider()
        translated, source_language_code = await translator.translate_to_english(body.raw_text)
        return TranslateTextResponse(
            translated_text=translated,
            source_language_code=source_language_code,
        )
    except TranslationConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except TranslationServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/experiences/tts", response_model=TextToSpeechResponse)
async def text_to_speech_experience(
    body: TextToSpeechRequest,
    current_user: Person = Depends(get_current_user),
):
    """Convert text to speech using Sarvam TTS (for speaking AI replies in builder chat)."""
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech is not configured. Set SARVAM_API_KEY.",
        )
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    max_chars = getattr(settings, "sarvam_tts_max_chars", 2500)
    if len(text) > max_chars:
        text = text[:max_chars]
    payload = {
        "text": text,
        "target_language_code": getattr(settings, "sarvam_tts_language_code", "en-IN"),
        "speaker": getattr(settings, "sarvam_tts_speaker", "shubh"),
        "model": getattr(settings, "sarvam_tts_model", "bulbul:v3"),
    }
    url = getattr(settings, "sarvam_tts_url", "https://api.sarvam.ai/text-to-speech")
    headers = {
        "api-subscription-key": settings.sarvam_api_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Sarvam TTS HTTP error %s: %s", e.response.status_code, e.response.text[:500])
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech service unavailable. Please try again.",
        ) from e
    except httpx.RequestError as e:
        logger.warning("Sarvam TTS request error: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech service unavailable. Please try again.",
        ) from e
    audios = data.get("audios") if isinstance(data, dict) else None
    if not audios or not isinstance(audios, list):
        raise HTTPException(status_code=503, detail="Invalid TTS response.")
    audio_base64 = "".join(audios) if audios else ""
    if not audio_base64:
        raise HTTPException(status_code=503, detail="No audio returned.")
    return TextToSpeechResponse(audio_base64=audio_base64)


async def _get_ws_user(token: str | None) -> Person | None:
    """Authenticate websocket user from JWT token query param."""
    if not token:
        return None
    user_id = decode_access_token(token.strip())
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(Person).where(Person.id == user_id))
        return result.scalar_one_or_none()


@router.websocket("/experiences/transcribe/stream")
async def stream_transcribe_experience_audio(websocket: WebSocket):
    """
    Proxy browser audio chunks to Sarvam streaming STT and stream transcript events back.

    Client message contract:
      - {"type":"audio_chunk","data":"<base64_pcm_or_wav>","sample_rate":16000}
      - {"type":"flush"}
      - {"type":"stop"}
    """
    user = await _get_ws_user(websocket.query_params.get("token"))
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authenticated")
        return

    await websocket.accept()

    try:
        speech = get_speech_provider()
    except SpeechConfigError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Speech service not configured")
        return

    sarvam_ws = None
    requested_language_code = (
        websocket.query_params.get("language_code")
        or websocket.query_params.get("lang")
    )
    try:
        sarvam_ws = await speech.connect(language_code=requested_language_code)
    except SpeechServiceError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Speech service unavailable")
        return
    except Exception as e:
        logger.exception("Unexpected speech connect error: %s", e)
        await websocket.send_json({"type": "error", "detail": "Speech service unavailable. Please try again later."})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Speech service unavailable")
        return

    async def client_to_sarvam() -> None:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                continue
            msg_type = str(payload.get("type") or "").strip().lower()

            if msg_type == "audio_chunk":
                b64_audio = payload.get("data")
                if not isinstance(b64_audio, str) or not b64_audio.strip():
                    continue
                sample_rate = payload.get("sample_rate")
                if isinstance(sample_rate, int):
                    chunk_rate = sample_rate
                elif isinstance(sample_rate, str) and sample_rate.isdigit():
                    chunk_rate = int(sample_rate)
                else:
                    chunk_rate = speech.sample_rate
                wav_audio = _normalize_audio_chunk_to_wav_b64(b64_audio, chunk_rate)
                if not wav_audio:
                    continue

                sarvam_payload = {
                    "audio": {
                        "data": wav_audio,
                        "sample_rate": chunk_rate,
                        "encoding": "audio/wav",
                    }
                }
                await sarvam_ws.send(json.dumps(sarvam_payload))
                continue

            if msg_type == "flush":
                await sarvam_ws.send(json.dumps({"type": "flush"}))
                continue

            if msg_type == "stop":
                await sarvam_ws.send(json.dumps({"type": "flush"}))
                return

    async def sarvam_to_client() -> None:
        while True:
            try:
                raw = await sarvam_ws.recv()
            except ConnectionClosedOK:
                # Upstream closed normally (e.g., after flush/stop).
                return
            except ConnectionClosed as e:
                # Treat going-away closes as normal termination as well.
                if getattr(e, "code", None) in {1000, 1001}:
                    return
                raise
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue

            msg_type = str(parsed.get("type") or "").strip().lower()
            data = parsed.get("data")
            if msg_type == "data" and isinstance(data, dict):
                transcript = data.get("transcript")
                if isinstance(transcript, str) and transcript.strip():
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "transcript": transcript,
                            "request_id": data.get("request_id"),
                        }
                    )
                continue
            if msg_type == "events":
                await websocket.send_json({"type": "event", "event": data})
                continue
            if msg_type == "error":
                detail = "Speech transcription failed."
                if isinstance(data, dict):
                    for key in ("error", "message", "detail"):
                        val = data.get(key)
                        if isinstance(val, str) and val.strip():
                            detail = val.strip()
                            break
                elif isinstance(data, str) and data.strip():
                    detail = data.strip()
                logger.warning("Builder transcribe upstream error: %s", detail)
                await websocket.send_json({"type": "error", "detail": detail})
                continue

    sender = asyncio.create_task(client_to_sarvam())
    receiver = asyncio.create_task(sarvam_to_client())
    try:
        done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        upstream_closed_abruptly = False
        for task in done:
            err = task.exception()
            if err is None:
                continue
            if isinstance(err, (WebSocketDisconnect, ConnectionClosedOK)):
                continue
            if isinstance(err, ConnectionClosed):
                upstream_closed_abruptly = True
                continue
            raise err
        if upstream_closed_abruptly:
            logger.info("Builder transcribe upstream connection closed (no close frame)")
            try:
                await websocket.send_json({"type": "error", "detail": "Live transcription session ended unexpectedly."})
            except Exception:
                pass
    except WebSocketDisconnect:
        logger.info("Builder transcribe websocket disconnected by client")
    except Exception as e:
        logger.exception("Builder transcribe websocket failure: %s", e)
        try:
            await websocket.send_json({"type": "error", "detail": "Live transcription session ended unexpectedly."})
        except Exception:
            pass
    finally:
        try:
            if sarvam_ws is not None:
                await sarvam_ws.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/experience-cards/detect-experiences", response_model=DetectExperiencesResponse)
async def detect_experiences_endpoint(
    body: RawExperienceCreate,
    current_user: Person = Depends(get_current_user),
):
    """Analyze text and return count + list of distinct experiences (for user to choose one)."""
    try:
        result = await detect_experiences(body.raw_text or "")
        return DetectExperiencesResponse(
            count=result.get("count", 0),
            experiences=[{"index": e["index"], "label": e["label"], "suggested": e.get("suggested", False)} for e in result.get("experiences", [])],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("detect-experiences failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))



@router.post("/experience-cards/draft-v1-single", response_model=DraftSetV1Response)
async def create_draft_single_experience(
    body: DraftSingleRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract and draft ONE experience by index (1-based). Process one experience at a time."""
    try:
        draft_set_id, raw_experience_id, card_families = await run_draft_v1_single(
            db,
            current_user.id,
            body.raw_text or "",
            body.experience_index,
            body.experience_count or 1,
        )
        return DraftSetV1Response(
            draft_set_id=draft_set_id,
            raw_experience_id=raw_experience_id,
            card_families=[CardFamilyV1Response(parent=f["parent"], children=f["children"]) for f in card_families],
        )
    except (ChatServiceError, EmbeddingServiceError, PipelineError) as e:
        logger.exception("draft-v1-single pipeline failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        logger.warning("draft-v1-single pipeline config error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


def _is_empty(v) -> bool:
    """True if value is considered empty (for merge: only fill empty fields)."""
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, bool):
        return False  # never overwrite booleans from "empty"
    return False


def _merged_form(current: dict, filled: dict, string_only_keys: tuple) -> dict:
    """Merge filled into current: only set keys where current is empty. Returns new dict."""
    out = dict(current)
    for k in string_only_keys:
        if k not in filled:
            continue
        if _is_empty(out.get(k)):
            out[k] = filled[k]
    return out


def _parse_date_for_patch(value: Any) -> Optional[date]:
    """Parse date from merged form (YYYY-MM-DD or YYYY-MM). Clarify can return YYYY-MM."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s[:10]
    if len(s) == 7 and s[4] == "-":  # YYYY-MM
        s = f"{s}-01"
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parent_merged_to_patch(merged: dict) -> ExperienceCardPatch:
    """Build ExperienceCardPatch from frontend form dict (merged)."""
    intent_secondary = None
    if merged.get("intent_secondary_str") is not None:
        s = merged["intent_secondary_str"]
        if isinstance(s, str):
            intent_secondary = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            intent_secondary = [str(x).strip() for x in s if str(x).strip()]
    start_date = _parse_date_for_patch(merged.get("start_date"))
    end_date = _parse_date_for_patch(merged.get("end_date"))
    confidence_score = None
    if merged.get("confidence_score") is not None and str(merged["confidence_score"]).strip():
        try:
            confidence_score = float(merged["confidence_score"])
        except (ValueError, TypeError):
            pass
    location_val = merged.get("location")
    if isinstance(location_val, dict) and "text" in location_val:
        location_val = location_val.get("text") or None
    elif not isinstance(location_val, str):
        location_val = None
    return ExperienceCardPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        normalized_role=merged.get("normalized_role") or None,
        domain=merged.get("domain") or None,
        sub_domain=merged.get("sub_domain") or None,
        company_name=merged.get("company_name") or None,
        company_type=merged.get("company_type") or None,
        location=location_val,
        employment_type=merged.get("employment_type") or None,
        start_date=start_date,
        end_date=end_date,
        is_current=merged.get("is_current") if isinstance(merged.get("is_current"), bool) else None,
        intent_primary=merged.get("intent_primary") or None,
        intent_secondary=intent_secondary,
        seniority_level=merged.get("seniority_level") or None,
        confidence_score=confidence_score,
        experience_card_visibility=merged.get("experience_card_visibility") if isinstance(merged.get("experience_card_visibility"), bool) else None,
    )


def _child_merged_to_patch(merged: dict) -> ExperienceCardChildPatch:
    """Build ExperienceCardChildPatch from frontend form dict (merged)."""
    tags = None
    if merged.get("tagsStr") is not None:
        s = merged["tagsStr"]
        if isinstance(s, str):
            tags = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            tags = [str(x).strip() for x in s if str(x).strip()]
    location_val = merged.get("location")
    if isinstance(location_val, dict) and "text" in location_val:
        location_val = location_val.get("text") or None
    elif not isinstance(location_val, str):
        location_val = None
    return ExperienceCardChildPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        tags=tags,
        time_range=merged.get("time_range") or None,
        location=location_val,
    )


# Keys we merge for parent (string-like; booleans handled in _parent_merged_to_patch)
_PARENT_MERGE_KEYS = (
    "title", "summary", "normalized_role", "domain", "sub_domain", "company_name", "company_type",
    "location", "employment_type", "start_date", "end_date", "intent_primary", "intent_secondary_str",
    "seniority_level", "confidence_score",
)
_CHILD_MERGE_KEYS = ("title", "summary", "tagsStr", "time_range", "location")


@router.post("/experience-cards/fill-missing-from-text", response_model=FillFromTextResponse)
async def fill_missing_from_text(
    body: FillFromTextRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rewrite + fill only missing fields from text. If card_id or child_id provided, persist to DB."""
    try:
        filled = await fill_missing_fields_from_text(
            raw_text=body.raw_text,
            current_card=body.current_card or {},
            card_type=body.card_type or "parent",
        )
    except HTTPException:
        raise

    current = body.current_card or {}
    if body.card_id and body.card_type == "parent":
        merged = _merged_form(current, filled, _PARENT_MERGE_KEYS)
        # Persist to DB
        card = await experience_card_service.get_card(db, body.card_id, current_user.id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        patch = _parent_merged_to_patch(merged)
        apply_card_patch(card, patch)
        await db.flush()
        await _reembed_cards_after_update(db, parents=[card], context="fill-missing (parent)")

    if body.child_id and body.card_type == "child":
        merged = _merged_form(current, filled, _CHILD_MERGE_KEYS)
        result = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.id == body.child_id,
                ExperienceCardChild.person_id == current_user.id,
            )
        )
        child = result.scalar_one_or_none()
        if not child:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child card not found")
        patch = _child_merged_to_patch(merged)
        apply_child_patch(child, patch)
        await db.flush()
        await _reembed_cards_after_update(db, children=[child], context="fill-missing (child)")

    return FillFromTextResponse(filled=filled)


@router.post("/experience-cards/clarify-experience", response_model=ClarifyExperienceResponse)
async def clarify_experience(
    body: ClarifyExperienceRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Interactive clarification: planner -> validate -> question writer / answer applier. Optionally persist when filled."""
    conv = [{"role": m.role, "content": m.content} for m in body.conversation_history]
    max_parent = body.max_parent_questions if body.max_parent_questions is not None else DEFAULT_MAX_PARENT_CLARIFY
    max_child = body.max_child_questions if body.max_child_questions is not None else DEFAULT_MAX_CHILD_CLARIFY
    try:
        result = await clarify_experience_interactive(
            raw_text=body.raw_text,
            current_card=body.current_card or {},
            card_type=body.card_type or "parent",
            conversation_history=conv,
            card_family=body.card_family,
            asked_history_structured=body.asked_history,
            last_question_target=body.last_question_target,
            max_parent=max_parent,
            max_child=max_child,
            card_families=body.card_families,
            focus_parent_id=body.focus_parent_id,
            detected_experiences=body.detected_experiences,
        )
    except HTTPException:
        raise

    clarifying_question = result.get("clarifying_question") or None
    filled = result.get("filled") or {}
    action = result.get("action")
    message = result.get("message")
    options = result.get("options")
    focus_parent_id_resp = result.get("focus_parent_id")

    current = body.current_card or {}
    if filled and body.card_id and body.card_type == "parent":
        merged = _merged_form(current, filled, _PARENT_MERGE_KEYS)
        card = await experience_card_service.get_card(db, body.card_id, current_user.id)
        if card:
            patch = _parent_merged_to_patch(merged)
            apply_card_patch(card, patch)
            await db.flush()
            await _reembed_cards_after_update(db, parents=[card], context="clarify (parent)")

    if filled and body.child_id and body.card_type == "child":
        merged = _merged_form(current, filled, _CHILD_MERGE_KEYS)
        child_row = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.id == body.child_id,
                ExperienceCardChild.person_id == current_user.id,
            )
        )
        child = child_row.scalar_one_or_none()
        if child:
            patch = _child_merged_to_patch(merged)
            apply_child_patch(child, patch)
            await db.flush()
            await _reembed_cards_after_update(db, children=[child], context="clarify (child)")

    return ClarifyExperienceResponse(
        clarifying_question=clarifying_question,
        filled=filled,
        action=action,
        message=message,
        options=options,
        focus_parent_id=focus_parent_id_resp,
        should_stop=result.get("should_stop"),
        stop_reason=result.get("stop_reason"),
        target_type=result.get("target_type"),
        target_field=result.get("target_field"),
        target_child_type=result.get("target_child_type"),
        progress=result.get("progress"),
        missing_fields=result.get("missing_fields"),
        asked_history_entry=result.get("asked_history_entry"),
        canonical_family=result.get("canonical_family"),
    )


@router.post("/experience-cards/finalize", response_model=ExperienceCardResponse)
async def finalize_experience_card(
    body: FinalizeExperienceCardRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finalize a drafted experience card:
    - Ensure it belongs to the current user
    - Mark it visible
    - Embed parent + children so it appears in search and \"Your Cards\".
    """
    card = await experience_card_service.get_card(db, body.card_id, current_user.id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Mark card as visible (was created as non-visible draft by the pipeline)
    card.experience_card_visibility = True

    # Load all children for this card so they are embedded together.
    children_result = await db.execute(
        select(ExperienceCardChild).where(
            ExperienceCardChild.parent_experience_id == card.id,
            ExperienceCardChild.person_id == current_user.id,
        )
    )
    children = children_result.scalars().all()

    await _reembed_cards_after_update(
        db,
        parents=[card],
        children=children,
        context="finalize",
    )

    return experience_card_to_response(card)


@router.post("/experience-cards", response_model=ExperienceCardResponse)
async def create_experience_card(
    body: ExperienceCardCreate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await experience_card_service.create_card(db, current_user.id, body)
    return experience_card_to_response(card)


@router.patch("/experience-cards/{card_id}", response_model=ExperienceCardResponse)
async def patch_experience_card(
    body: ExperienceCardPatch,
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    apply_card_patch(card, body)
    await _reembed_cards_after_update(db, parents=[card], context="PATCH card")
    return experience_card_to_response(card)


@router.delete("/experience-cards/{card_id}", response_model=ExperienceCardResponse)
async def delete_experience_card(
    card: ExperienceCard = Depends(get_experience_card_or_404),
    db: AsyncSession = Depends(get_db),
):
    # Delete all children first so they are removed when parent is deleted (explicit cascade)
    await db.execute(delete(ExperienceCardChild).where(ExperienceCardChild.parent_experience_id == card.id))
    response = experience_card_to_response(card)
    await db.delete(card)
    return response


@router.patch(
    "/experience-card-children/{child_id}",
    response_model=ExperienceCardChildResponse,
)
async def patch_experience_card_child(
    body: ExperienceCardChildPatch,
    child: ExperienceCardChild = Depends(get_experience_card_child_or_404),
    db: AsyncSession = Depends(get_db),
):
    apply_child_patch(child, body)
    await _reembed_cards_after_update(db, children=[child], context="PATCH child")
    return experience_card_child_to_response(child)


@router.delete(
    "/experience-card-children/{child_id}",
    response_model=ExperienceCardChildResponse,
)
async def delete_experience_card_child(
    child: ExperienceCardChild = Depends(get_experience_card_child_or_404),
    db: AsyncSession = Depends(get_db),
):
    response = experience_card_child_to_response(child)
    await db.delete(child)
    return response
