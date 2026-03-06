from openai import AsyncOpenAI
from app.core.config import settings
_client: AsyncOpenAI | None = None



def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.embedding_api_url)
    return _client


async def get_embedding(text: str) -> list[float]:
    """Return the embedding vector for *text*."""
    client = _get_client()
    response = await client.embeddings.create(input=text, model=settings.embedding_model)
    return response.data[0].embedding

