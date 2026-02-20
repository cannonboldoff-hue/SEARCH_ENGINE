import logging
from functools import lru_cache
from typing import Any

import httpx

from src.core import get_settings

logger = logging.getLogger(__name__)


class OtpServiceError(Exception):
    """Raised when the OTP service fails or returns an unexpected response."""


class OtpRateLimitError(OtpServiceError):
    """Raised when the OTP service rate-limits a request."""


class OtpConfigError(OtpServiceError):
    """Raised when OTP configuration is missing or invalid."""


class TwilioVerifyProvider:
    def __init__(self, account_sid: str, auth_token: str, service_sid: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.service_sid = service_sid
        self.base_url = f"https://verify.twilio.com/v2/Services/{service_sid}"

    async def _post(self, path: str, data: dict[str, Any]) -> dict:
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, data=data, auth=(self.account_sid, self.auth_token))
                if r.status_code == 429:
                    raise OtpRateLimitError("OTP provider rate-limited the request.")
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            body = getattr(e.response, "text", None) or ""
            if body:
                logger.warning("Twilio Verify error %s: %s", e.response.status_code, body[:500])
            raise OtpServiceError("OTP service returned an error.") from e
        except httpx.RequestError as e:
            raise OtpServiceError("OTP service unavailable.") from e
        except ValueError as e:
            raise OtpServiceError("OTP service returned invalid JSON.") from e

    async def start_verification(self, to: str, channel: str = "sms") -> None:
        await self._post("Verifications", {"To": to, "Channel": channel})

    async def check_verification(self, to: str, code: str) -> bool:
        data = await self._post("VerificationCheck", {"To": to, "Code": code})
        status = str(data.get("status", "")).lower()
        if data.get("valid") is True:
            return True
        return status == "approved"


@lru_cache
def get_otp_provider() -> TwilioVerifyProvider:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_verify_service_sid):
        raise OtpConfigError("OTP service not configured.")
    return TwilioVerifyProvider(
        account_sid=s.twilio_account_sid,
        auth_token=s.twilio_auth_token,
        service_sid=s.twilio_verify_service_sid,
    )
