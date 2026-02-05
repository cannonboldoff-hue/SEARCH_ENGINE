import asyncio
import json
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from src.config import get_settings


class ChatServiceError(Exception):
    """Raised when the chat/LLM API is unavailable or returns invalid or unexpected output."""


class ChatRateLimitError(ChatServiceError):
    """Raised when the chat/LLM API rate limits the request."""


class ParsedQuery(BaseModel):
    company: str | None = None
    team: str | None = None
    open_to_work_only: bool = False
    semantic_text: str = ""


class ChatProvider(ABC):
    @abstractmethod
    async def parse_search_query(self, query: str) -> ParsedQuery:
        pass

    async def chat(self, user_message: str, max_tokens: int = 2048) -> str:
        """Send a single user message and return the assistant reply. Override if needed."""
        return await self._chat([{"role": "user", "content": user_message}], max_tokens=max_tokens)


class OpenAICompatibleChatProvider(ChatProvider):
    """OpenAI-compatible endpoint (vLLM, etc.)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
    ):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"
        self.api_key = api_key
        self.model = model

    async def _chat(self, messages: list[dict[str, str]], max_tokens: int = 2048) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        retries = 3
        base_delay_s = 1.0

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    r.raise_for_status()
                    data = r.json()
                    choices = data.get("choices") or []
                    if not choices:
                        raise ChatServiceError(
                            "Chat API returned no choices (e.g. content filter)."
                        )
                    msg = choices[0].get("message") or {}
                    content = msg.get("content")
                    if content is None or not isinstance(content, str):
                        raise ChatServiceError(
                            "Chat API returned missing or non-string content."
                        )
                    return content.strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    if attempt < retries:
                        retry_after = e.response.headers.get("Retry-After")
                        try:
                            delay_s = float(retry_after) if retry_after else base_delay_s
                        except ValueError:
                            delay_s = base_delay_s
                        await asyncio.sleep(delay_s * (attempt + 1))
                        continue
                    raise ChatRateLimitError(
                        "Chat API rate limited the request. Please retry later."
                    ) from e
                raise ChatServiceError(
                    f"Chat API returned {e.response.status_code}. Please try again later."
                ) from e
            except httpx.RequestError as e:
                raise ChatServiceError(
                    "Chat service unavailable (timeout or connection error). Please try again later."
                ) from e
            except (KeyError, TypeError, IndexError) as e:
                raise ChatServiceError("Chat API returned unexpected response format.") from e

    async def parse_search_query(self, query: str) -> ParsedQuery:
        prompt = f"""Parse this search query into structured filters and semantic text. Output JSON only, no markdown.
Query: "{query}"

Extract:
- company: company name if mentioned (e.g. Razorpay), else null
- team: team/department if mentioned (e.g. backend), else null
- open_to_work_only: true if query implies "wants a job" / "looking for work", else false
- semantic_text: the full query normalized for semantic search (keep intent, remove filler)

Output format: {{"company": null or "string", "team": null or "string", "open_to_work_only": false, "semantic_text": "string"}}"""
        try:
            text = await self._chat([{"role": "user", "content": prompt}], max_tokens=300)
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            data = json.loads(text)
        except (ValueError, json.JSONDecodeError) as e:
            raise ChatServiceError("Chat returned invalid JSON for query parse.") from e
        return ParsedQuery(
            company=data.get("company"),
            team=data.get("team"),
            open_to_work_only=bool(data.get("open_to_work_only", False)),
            semantic_text=data.get("semantic_text", query),
        )


class OpenAIChatProvider(OpenAICompatibleChatProvider):
    """Official OpenAI API."""

    def __init__(self):
        s = get_settings()
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=s.openai_api_key,
            model=s.chat_model or _OPENAI_DEFAULT_MODEL,
        )


# Default model for OpenAI official API when CHAT_MODEL is not set
_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
# Default model for OpenAI-compatible (vLLM, etc.) when CHAT_MODEL is not set
_OPENAI_COMPATIBLE_DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def get_chat_provider() -> ChatProvider:
    s = get_settings()
    if s.openai_api_key and not s.chat_api_base_url:
        return OpenAIChatProvider()
    if s.chat_api_base_url:
        return OpenAICompatibleChatProvider(
            base_url=s.chat_api_base_url,
            api_key=s.chat_api_key,
            model=s.chat_model or _OPENAI_COMPATIBLE_DEFAULT_MODEL,
        )
    raise RuntimeError(
        "Chat LLM not configured. Set OPENAI_API_KEY or CHAT_API_BASE_URL (and CHAT_MODEL)."
    )
