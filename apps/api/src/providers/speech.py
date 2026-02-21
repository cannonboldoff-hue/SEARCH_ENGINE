import logging
import re
from urllib.parse import urlencode

import websockets

from src.core import get_settings

logger = logging.getLogger(__name__)


class SpeechServiceError(Exception):
    """Raised when the speech provider is unavailable or fails unexpectedly."""


class SpeechConfigError(SpeechServiceError):
    """Raised when speech provider configuration is missing."""


class SarvamStreamingSpeechProvider:
    """Thin connection helper for Sarvam streaming STT websocket API."""

    def __init__(
        self,
        *,
        api_key: str,
        ws_url: str,
        model: str,
        language_code: str,
        sample_rate: int,
        input_audio_codec: str,
    ):
        self.api_key = api_key
        self.ws_url = ws_url.rstrip("?")
        self.model = model
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.input_audio_codec = input_audio_codec

    @staticmethod
    def _normalize_language_code(language_code: str | None) -> str | None:
        if language_code is None:
            return None
        code = language_code.strip()
        if not code:
            return None
        if code.lower() == "unknown":
            return None  # use default (e.g. en-IN) instead of sending "unknown" to Sarvam
        if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", code):
            return code
        return None

    def build_url(self, *, language_code: str | None = None) -> str:
        resolved_language = (
            self._normalize_language_code(language_code)
            or self._normalize_language_code(self.language_code)
            or "en-IN"
        )
        params = {
            "language-code": resolved_language,
            "model": self.model,
            "sample_rate": str(self.sample_rate),
            "input_audio_codec": self.input_audio_codec,
        }
        return f"{self.ws_url}?{urlencode(params)}"

    async def connect(self, *, language_code: str | None = None):
        url = self.build_url(language_code=language_code)
        headers = {"Api-Subscription-Key": self.api_key}
        try:
            return await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            # Compatibility fallback for older websockets versions.
            return await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
        except Exception as e:
            logger.exception("Sarvam websocket connect failed: %s", e)
            raise SpeechServiceError("Speech service unavailable. Please try again later.") from e


def get_speech_provider() -> SarvamStreamingSpeechProvider:
    s = get_settings()
    if not s.sarvam_api_key:
        raise SpeechConfigError("Sarvam STT not configured. Set SARVAM_API_KEY.")
    return SarvamStreamingSpeechProvider(
        api_key=s.sarvam_api_key,
        ws_url=s.sarvam_stt_ws_url,
        model=s.sarvam_stt_model,
        language_code=s.sarvam_stt_language_code,
        sample_rate=s.sarvam_stt_sample_rate,
        input_audio_codec=s.sarvam_stt_input_audio_codec,
    )
