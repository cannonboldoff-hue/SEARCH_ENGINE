from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from src.config import get_settings


class ParsedQuery(BaseModel):
    company: str | None = None
    team: str | None = None
    open_to_work_only: bool = False
    semantic_text: str = ""


class DraftCard(BaseModel):
    draft_card_id: str
    title: str | None = None
    context: str | None = None
    constraints: str | None = None
    decisions: str | None = None
    outcome: str | None = None
    tags: list[str] = []
    company: str | None = None
    team: str | None = None
    role_title: str | None = None
    time_range: str | None = None
    source_span: str | None = None


class DraftSet(BaseModel):
    draft_set_id: str
    raw_experience_id: str
    cards: list[DraftCard] = []


class ChatProvider(ABC):
    @abstractmethod
    async def parse_search_query(self, query: str) -> ParsedQuery:
        pass

    @abstractmethod
    async def extract_experience_cards(self, raw_text: str, raw_experience_id: str) -> DraftSet:
        pass


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
            self.base_url = self.base_url + "/v1" if not self.base_url.endswith("/v1") else self.base_url
        self.api_key = api_key
        self.model = model

    async def _chat(self, messages: list[dict[str, str]], max_tokens: int = 2048) -> str:
        import httpx
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

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
            import json
            # strip markdown code block if present
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            data = json.loads(text)
            return ParsedQuery(
                company=data.get("company"),
                team=data.get("team"),
                open_to_work_only=bool(data.get("open_to_work_only", False)),
                semantic_text=data.get("semantic_text", query),
            )
        except Exception:
            return ParsedQuery(semantic_text=query)

    async def extract_experience_cards(self, raw_text: str, raw_experience_id: str) -> DraftSet:
        import uuid
        import json
        prompt = f"""Extract work experience cards from this paragraph. One paragraph may contain multiple distinct experiences (different companies, roles, or time periods). Output strict JSON only.

Paragraph:
---
{raw_text}
---

Output a single JSON object:
{{
  "draft_set_id": "<uuid>",
  "raw_experience_id": "{raw_experience_id}",
  "cards": [
    {{
      "draft_card_id": "<uuid>",
      "title": "short title or null",
      "context": "context or null",
      "constraints": "constraints or null",
      "decisions": "decisions or null",
      "outcome": "outcome or null",
      "tags": ["tag1", "tag2"],
      "company": "company name or null",
      "team": "team or null",
      "role_title": "role or null",
      "time_range": "e.g. 2020-2022 or null",
      "source_span": "exact sentence or phrase this card came from, or null"
    }}
  ]
}}

Rules: Extract only what is explicitly stated. If a field is missing, use null. Do not polish or invent. Split into multiple cards if there are multiple distinct work episodes."""
        try:
            text = await self._chat([{"role": "user", "content": prompt}], max_tokens=2048)
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            data = json.loads(text)
            cards = [
                DraftCard(
                    draft_card_id=c.get("draft_card_id") or str(uuid.uuid4()),
                    title=c.get("title"),
                    context=c.get("context"),
                    constraints=c.get("constraints"),
                    decisions=c.get("decisions"),
                    outcome=c.get("outcome"),
                    tags=c.get("tags") or [],
                    company=c.get("company"),
                    team=c.get("team"),
                    role_title=c.get("role_title"),
                    time_range=c.get("time_range"),
                    source_span=c.get("source_span"),
                )
                for c in data.get("cards", [])
            ]
            return DraftSet(
                draft_set_id=data.get("draft_set_id") or str(uuid.uuid4()),
                raw_experience_id=raw_experience_id,
                cards=cards,
            )
        except Exception:
            return DraftSet(
                draft_set_id=str(uuid.uuid4()),
                raw_experience_id=raw_experience_id,
                cards=[
                    DraftCard(
                        draft_card_id=str(uuid.uuid4()),
                        title="Untitled",
                        context=raw_text[:500] if raw_text else None,
                        source_span=raw_text[:200] if raw_text else None,
                    )
                ],
            )


class OpenAIChatProvider(OpenAICompatibleChatProvider):
    """Official OpenAI API."""

    def __init__(self):
        s = get_settings()
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=s.openai_api_key,
            model=s.chat_model or "gpt-4o-mini",
        )


def get_chat_provider() -> ChatProvider:
    s = get_settings()
    if s.openai_api_key and not s.chat_api_base_url:
        return OpenAIChatProvider()
    if s.chat_api_base_url:
        return OpenAICompatibleChatProvider(
            base_url=s.chat_api_base_url,
            api_key=s.chat_api_key,
            model=s.chat_model,
        )
    return DummyChatProvider()


class DummyChatProvider(ChatProvider):
    """Heuristic fallback when no API configured."""

    async def parse_search_query(self, query: str) -> ParsedQuery:
        q = query.lower()
        company = None
        for w in ["razorpay", "google", "meta", "amazon", "microsoft"]:
            if w in q:
                company = w.capitalize()
                break
        team = None
        if "backend" in q:
            team = "backend"
        elif "frontend" in q:
            team = "frontend"
        open_to_work = "job" in q or "work" in q or "hiring" in q or "looking" in q
        return ParsedQuery(
            company=company,
            team=team,
            open_to_work_only=open_to_work,
            semantic_text=query,
        )

    async def extract_experience_cards(self, raw_text: str, raw_experience_id: str) -> DraftSet:
        import uuid
        import re
        draft_set_id = str(uuid.uuid4())
        cards = []
        # Split on common separators
        parts = re.split(r"\s*(?:Also|Then|;|\n\n|\d+\.)\s*", raw_text)
        for i, part in enumerate(parts):
            part = part.strip()
            if not part or len(part) < 10:
                continue
            company = None
            for m in re.finditer(r"(?:at|in|@)\s+([A-Z][a-zA-Z0-9\s]+?)(?:\s+as|\s+working|\s*\.|,|$)", part):
                company = m.group(1).strip()
                break
            if not company:
                company = "Unknown"
            cards.append(
                DraftCard(
                    draft_card_id=str(uuid.uuid4()),
                    title=part[:80] + "..." if len(part) > 80 else part,
                    context=part,
                    company=company,
                    source_span=part[:200],
                )
            )
        if not cards:
            cards.append(
                DraftCard(
                    draft_card_id=str(uuid.uuid4()),
                    title="Untitled",
                    context=raw_text,
                    source_span=raw_text[:200],
                )
            )
        return DraftSet(draft_set_id=draft_set_id, raw_experience_id=raw_experience_id, cards=cards)
