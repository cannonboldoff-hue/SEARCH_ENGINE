from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from apps/api so it works regardless of CWD
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    database_url: str = "postgresql://localhost/conxa"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Chat (OpenAI-compatible open-source); None => provider-specific default
    chat_api_base_url: str | None = None
    chat_api_key: str | None = None
    chat_model: str | None = None

    # Embeddings (OpenAI-compatible; text-embedding-3-large uses 3072 dims, run migration if changing)
    embed_api_base_url: str | None = None
    embed_api_key: str | None = None
    embed_model: str = "text-embedding-3-large"
    embed_dimension: int = 324  # match DB (migration 018)

    openai_api_key: str | None = None

    # Sarvam streaming speech-to-text
    sarvam_api_key: str | None = None
    sarvam_stt_ws_url: str = "wss://api.sarvam.ai/speech-to-text/ws"
    sarvam_stt_model: str = "saarika:v2.5"
    sarvam_stt_language_code: str = "en-IN"
    sarvam_stt_sample_rate: int = 16000
    sarvam_stt_input_audio_codec: str = "pcm_s16le"

    # Sarvam text-to-speech (optional; for speaking AI replies in builder chat)
    sarvam_tts_url: str = "https://api.sarvam.ai/text-to-speech"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"
    sarvam_tts_language_code: str = "en-IN"
    sarvam_tts_max_chars: int = 2500

    # Sarvam text translation (for multilingual-to-English normalization)
    sarvam_translate_url: str = "https://api.sarvam.ai/translate"
    sarvam_text_lid_url: str = "https://api.sarvam.ai/text-lid"
    sarvam_translate_model: str = "mayura:v1"
    sarvam_translate_source_language_code: str = "auto"
    sarvam_translate_target_language_code: str = "en-IN"
    sarvam_translate_mode: str | None = None
    sarvam_translate_max_chars: int = 900

    # Rate limiting (per-user when key_func uses user id; multi-instance needs Redis later)
    search_rate_limit: str = "10/minute"
    unlock_rate_limit: str = "30/minute"
    auth_login_rate_limit: str = "10/minute"
    auth_signup_rate_limit: str = "5/minute"
    auth_verify_rate_limit: str = "10/minute"

    # OTP (Twilio Verify)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_verify_service_sid: str | None = None
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    otp_max_sends: int = 5
    otp_resend_cooldown_seconds: int = 30

    # Email verification (SendGrid)
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str | None = None
    sendgrid_from_name: str | None = None
    email_verify_url_base: str | None = None
    email_verify_expire_minutes: int = 30
    email_verification_required: bool = False

    # CORS (comma-separated origins; * allows all)
    cors_origins: str = "*"

    # Profile photo uploads (directory path; created if missing)
    profile_photos_upload_dir: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed CORS origins for middleware."""
        raw = self.cors_origins.strip()
        return ["*"] if not raw else [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
