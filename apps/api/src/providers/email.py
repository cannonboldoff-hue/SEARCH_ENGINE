import logging
from functools import lru_cache
from typing import Any

import httpx

from src.core import get_settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when the email service fails or returns an unexpected response."""


class EmailConfigError(EmailServiceError):
    """Raised when email configuration is missing or invalid."""


class SendGridProvider:
    def __init__(self, api_key: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.base_url = "https://api.sendgrid.com/v3/mail/send"

    async def send_email(self, to_email: str, subject: str, text: str, html: str | None = None) -> None:
        content: list[dict[str, Any]] = [{"type": "text/plain", "value": text}]
        if html:
            content.append({"type": "text/html", "value": html})

        from_payload: dict[str, Any] = {"email": self.from_email}
        if self.from_name:
            from_payload["name"] = self.from_name

        payload = {
            "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
            "from": from_payload,
            "content": content,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(self.base_url, json=payload, headers=headers)
                r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = getattr(e.response, "text", None) or ""
            if body:
                logger.warning("SendGrid error %s: %s", e.response.status_code, body[:500])
            raise EmailServiceError("Email service returned an error.") from e
        except httpx.RequestError as e:
            raise EmailServiceError("Email service unavailable.") from e


@lru_cache
def get_email_provider() -> SendGridProvider:
    s = get_settings()
    if not (s.sendgrid_api_key and s.sendgrid_from_email):
        raise EmailConfigError("Email service not configured.")
    return SendGridProvider(
        api_key=s.sendgrid_api_key,
        from_email=s.sendgrid_from_email,
        from_name=s.sendgrid_from_name,
    )
