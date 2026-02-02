from abc import ABC, abstractmethod
from typing import List
from src.config import get_settings


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        pass


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible /embeddings endpoint."""

    def __init__(self, base_url: str, api_key: str | None, model: str, dimension: int = 384):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = self.base_url + "/v1" if "/v1" not in self.base_url else self.base_url
        self.api_key = api_key
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: List[str]) -> List[List[float]]:
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


class DummyEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based vector when no API available."""

    dimension = 384

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib
        result = []
        for t in texts:
            h = hashlib.sha256(t.encode()).hexdigest()
            vec = []
            for i in range(0, min(len(h), self.dimension * 2), 2):
                vec.append((int(h[i : i + 2], 16) / 255.0) * 2 - 1)
            while len(vec) < self.dimension:
                vec.append(0.0)
            result.append(vec[: self.dimension])
        return result


def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.embed_api_base_url:
        return OpenAICompatibleEmbeddingProvider(
            base_url=s.embed_api_base_url,
            api_key=s.embed_api_key,
            model=s.embed_model,
            dimension=384,
        )
    return DummyEmbeddingProvider()
