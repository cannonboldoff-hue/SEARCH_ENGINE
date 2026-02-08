import asyncio
import json
import logging
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from src.core import get_settings
from src.prompts.search_filters import (
    get_cleanup_prompt,
    get_single_extract_prompt,
)

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Raised when the chat/LLM API is unavailable or returns invalid or unexpected output."""


class ChatRateLimitError(ChatServiceError):
    """Raised when the chat/LLM API rate limits the request."""


class ParsedQuery(BaseModel):
    company: str | None = None
    team: str | None = None
    open_to_work_only: bool = False
    semantic_text: str = ""


def _strip_json_from_response(raw: str) -> str:
    """Strip markdown/code fences and return JSON string."""
    s = (raw or "").strip()
    if "```" in s:
        parts = s.split("```")
        for p in parts:
            p = p.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                return p
    return s


class ChatProvider(ABC):
    @abstractmethod
    async def parse_search_query(self, query: str) -> ParsedQuery:
        pass

    @abstractmethod
    async def parse_search_filters(self, query: str) -> dict:
        """Cleanup → extract → validate; return full filters JSON for Search.filters."""
        pass

    async def chat(self, user_message: str, max_tokens: int = 20480, temperature: float | None = None) -> str:
        """Send a single user message and return the assistant reply. Override if needed."""
        return await self._chat(
            [{"role": "user", "content": user_message}],
            max_tokens=max_tokens,
            temperature=temperature,
        )


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

    async def _chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 20480,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature if temperature is not None else 0.2,
        }
        if response_format is not None:
            payload["response_format"] = response_format
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
                    stripped = content.strip()
                    if not stripped:
                        raise ChatServiceError(
                            "Chat API returned empty content (LLM may have failed or been rate-limited)."
                        )
                    return stripped
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
                body = getattr(e.response, "text", None) or ""
                if body:
                    logger.warning(
                        "Chat API error %s: %s",
                        e.response.status_code,
                        body[:500],
                    )
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
        prompt = """Parse the search query into structured constraints. Reply with a single JSON object only (no markdown, no code fence).

Schema:
- company: string or null — company name if mentioned (e.g. "Razorpay")
- team: string or null — team/department if mentioned (e.g. "backend")
- open_to_work_only: boolean — true only if the query clearly implies "looking for work" / "open to jobs"
- semantic_query_text: string — the query text normalized for semantic search (keep intent, remove filler)

Example: {"company": null, "team": "backend", "open_to_work_only": false, "semantic_query_text": "backend engineer with Go experience"}"""
        user_content = f'Query: "{query}"'
        messages = [{"role": "user", "content": prompt + "\n\n" + user_content}]
        text = None
        try:
            text = await self._chat(
                messages,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
        except ChatServiceError:
            # Some providers (e.g. Groq with certain models) return 400 for response_format
            logger.info(
                "Chat API rejected response_format=json_object, retrying without it."
            )
            text = await self._chat(messages, max_tokens=300, response_format=None)
        try:
            raw = (text or "").strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as e:
            raise ChatServiceError("Chat returned invalid JSON for query parse.") from e
        return ParsedQuery(
            company=data.get("company"),
            team=data.get("team"),
            open_to_work_only=bool(data.get("open_to_work_only", False)),
            semantic_text=data.get("semantic_query_text", data.get("semantic_text", query)),
        )

    async def _chat_json(self, messages: list[dict[str, str]], max_tokens: int = 4096) -> dict:
        """Call _chat and parse response as JSON; retry without response_format if needed."""
        try:
            text = await self._chat(
                messages,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except ChatServiceError:
            logger.info(
                "Chat API rejected response_format=json_object, retrying without it."
            )
            text = await self._chat(messages, max_tokens=max_tokens, response_format=None)
        raw = _strip_json_from_response(text or "")
        try:
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError) as e:
            raise ChatServiceError("Chat returned invalid JSON.") from e

    async def parse_search_filters(self, query: str) -> dict:
        """Cleanup → single extract; return JSON for Search.parsed_constraints_json (company_norm, team_norm, intent_primary, etc.)."""
        # 1) Cleanup (plain text only)
        cleanup_prompt = get_cleanup_prompt(query)
        cleaned_text = (await self._chat(
            [{"role": "user", "content": cleanup_prompt}],
            max_tokens=500,
            response_format=None,
        )).strip()
        if not cleaned_text:
            cleaned_text = query

        # 2) Single extraction (exact schema for parsed_constraints_json)
        extract_prompt = get_single_extract_prompt(query, cleaned_text)
        extracted = await self._chat_json(
            [{"role": "user", "content": extract_prompt}],
            max_tokens=4096,
        )
        if not isinstance(extracted, dict):
            raise ChatServiceError("Extract step did not return a JSON object.")

        return extracted


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
