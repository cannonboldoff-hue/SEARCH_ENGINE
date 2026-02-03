from abc import ABC, abstractmethod

from src.config import get_settings


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible /embeddings endpoint."""

    def __init__(self, base_url: str, api_key: str | None, model: str, dimension: int = 384):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"
        self.api_key = api_key
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx
        if not texts:
            return []
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            out = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
            if out:
                self._dimension = len(out[0])
            return out


def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.embed_api_base_url:
        return OpenAICompatibleEmbeddingProvider(
            base_url=s.embed_api_base_url,
            api_key=s.embed_api_key,
            model=s.embed_model,
            dimension=384,
        )
    raise RuntimeError(
        "Embedding model not configured. Set EMBED_API_BASE_URL (and EMBED_MODEL)."
    )
