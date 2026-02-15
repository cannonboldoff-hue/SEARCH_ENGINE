import logging
import re

import httpx

from src.core import get_settings

logger = logging.getLogger(__name__)


class TranslationServiceError(Exception):
    """Raised when translation service is unavailable or returns an invalid response."""


class TranslationConfigError(TranslationServiceError):
    """Raised when translation provider configuration is missing."""


class _TranslationHTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _split_text_for_translation(text: str, max_chars: int) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    if max_chars <= 0 or len(raw) <= max_chars:
        return [raw]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    def append_part(part: str, separator: str) -> None:
        nonlocal current
        if not part.strip():
            return
        candidate = part.strip() if not current else f"{current}{separator}{part.strip()}"
        if len(candidate) <= max_chars:
            current = candidate
            return
        if current:
            flush()
        if len(part) <= max_chars:
            current = part.strip()
            return
        for i in range(0, len(part), max_chars):
            segment = part[i:i + max_chars].strip()
            if segment:
                chunks.append(segment)

    paragraphs = [p.strip() for p in re.split(r"\n+", raw) if p.strip()]
    if not paragraphs:
        paragraphs = [raw]

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            append_part(paragraph, "\n")
            continue

        sentences = [s.strip() for s in re.split(r"(?<=[.!?\u0964])\s+", paragraph) if s.strip()]
        if not sentences:
            sentences = [paragraph]
        for sentence in sentences:
            append_part(sentence, " ")
    flush()
    return chunks


def _infer_language_from_script(text: str) -> str | None:
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te-IN"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi-IN"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta-IN"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn-IN"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml-IN"
    if re.search(r"[\u0A80-\u0AFF]", text):
        return "gu-IN"
    if re.search(r"[\u0A00-\u0A7F]", text):
        return "pa-IN"
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn-IN"
    if re.search(r"[\u0B00-\u0B7F]", text):
        return "od-IN"
    if re.search(r"[A-Za-z]", text):
        return "en-IN"
    return None


class SarvamTranslationProvider:
    """Thin helper for Sarvam text translation API."""

    def __init__(
        self,
        *,
        api_key: str,
        translate_url: str,
        text_lid_url: str,
        model: str,
        source_language_code: str,
        target_language_code: str,
        mode: str | None,
        max_chars: int,
    ):
        self.api_key = api_key
        self.translate_url = translate_url
        self.text_lid_url = text_lid_url
        self.model = model
        self.source_language_code = source_language_code
        self.target_language_code = target_language_code
        self.mode = mode
        self.max_chars = max_chars

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "api-subscription-key": self.api_key,
        }

    async def _detect_language(self, text: str) -> str | None:
        payload = {"input": text[:1000]}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(self.text_lid_url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("Sarvam text-lid failed; falling back to configured source language: %s", e)
            return None
        code = data.get("language_code")
        if isinstance(code, str) and code.strip():
            return code.strip()
        return None

    async def _translate_chunk(self, text: str, source_language_code: str) -> tuple[str, str | None]:
        payload: dict[str, str] = {
            "input": text,
            "source_language_code": source_language_code,
            "target_language_code": self.target_language_code,
            "model": self.model,
        }
        if self.mode:
            payload["mode"] = self.mode
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(self.translate_url, json=payload, headers=self._headers)
        except httpx.RequestError as e:
            raise TranslationServiceError("Sarvam translation service unavailable. Please try again later.") from e

        if response.status_code == 429:
            raise _TranslationHTTPError(response.status_code, "Sarvam translation rate limited. Please retry shortly.")
        if response.status_code >= 400:
            body = (response.text or "").strip()
            if body:
                logger.warning("Sarvam translate error %s: %s", response.status_code, body[:500])
            message = "Sarvam translation failed. Please try again later."
            try:
                parsed = response.json()
                err = parsed.get("error")
                if isinstance(err, dict):
                    msg = err.get("message")
                    if isinstance(msg, str) and msg.strip():
                        message = msg.strip()
            except ValueError:
                pass
            raise _TranslationHTTPError(response.status_code, message)

        try:
            data = response.json()
        except ValueError as e:
            raise TranslationServiceError("Sarvam translation returned invalid JSON.") from e

        translated_text = data.get("translated_text")
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise TranslationServiceError("Sarvam translation returned empty output.")
        detected_source = data.get("source_language_code")
        source_out = detected_source.strip() if isinstance(detected_source, str) and detected_source.strip() else None
        return translated_text.strip(), source_out

    async def translate_to_english(self, text: str) -> tuple[str, str | None]:
        raw = (text or "").strip()
        if not raw:
            raise TranslationServiceError("Text for translation cannot be empty.")

        configured_source_code = (self.source_language_code or "auto").strip()
        source_code = configured_source_code
        detected_source_code = None
        if source_code.lower() == "auto":
            detected_source_code = await self._detect_language(raw)
            if not detected_source_code:
                detected_source_code = _infer_language_from_script(raw)
            if detected_source_code:
                source_code = detected_source_code

        chunks = _split_text_for_translation(raw, self.max_chars)
        if not chunks:
            raise TranslationServiceError("Text for translation cannot be empty.")

        translated_chunks: list[str] = []
        response_source_code = detected_source_code
        for chunk in chunks:
            try:
                translated, source_from_response = await self._translate_chunk(chunk, source_code)
            except _TranslationHTTPError as e:
                if configured_source_code.lower() == "auto" and source_code.lower() == "auto" and e.status_code == 422:
                    retry_source = await self._detect_language(chunk) or _infer_language_from_script(chunk)
                    if retry_source:
                        source_code = retry_source
                        translated, source_from_response = await self._translate_chunk(chunk, source_code)
                    else:
                        raise TranslationServiceError(
                            "Sarvam translation could not detect source language. Please add more text."
                        ) from e
                else:
                    raise TranslationServiceError(e.message) from e
            translated_chunks.append(translated)
            if not response_source_code and source_from_response:
                response_source_code = source_from_response

        translated_text = "\n".join(t for t in translated_chunks if t).strip()
        if not translated_text:
            raise TranslationServiceError("Sarvam translation returned empty output.")
        return translated_text, response_source_code


def get_translation_provider() -> SarvamTranslationProvider:
    s = get_settings()
    if not s.sarvam_api_key:
        raise TranslationConfigError("Sarvam Translate not configured. Set SARVAM_API_KEY.")
    return SarvamTranslationProvider(
        api_key=s.sarvam_api_key,
        translate_url=s.sarvam_translate_url,
        text_lid_url=s.sarvam_text_lid_url,
        model=s.sarvam_translate_model,
        source_language_code=s.sarvam_translate_source_language_code,
        target_language_code=s.sarvam_translate_target_language_code,
        mode=s.sarvam_translate_mode,
        max_chars=s.sarvam_translate_max_chars,
    )
