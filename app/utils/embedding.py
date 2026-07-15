import httpx

from app import settings


async def embed_queries(texts: list[str], prompt_name: str | None = None) -> list[list[float]]:
    """Embed one or more texts via the Betterworks embedding service.

    Mirrors llm-engine's embedding client. For a job-description query vector,
    pass prompt_name='query'. Returns one 768-dim vector per input text, in the
    same order as `texts`.
    """
    body: dict = {"input": texts, "model": settings.EMBEDDING_MODEL}
    if prompt_name:
        body["prompt_name"] = prompt_name

    try:
        async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{settings.BW_EMBEDDING_URL}/v1/embeddings", json=body)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            "Embedding service returned %s: %s" % (exc.response.status_code, exc.response.text)
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Embedding service request failed: %s" % exc) from exc

    try:
        payload = resp.json()
        return [item["embedding"] for item in sorted(payload["data"], key=lambda x: x["index"])]
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError("Unexpected embedding service response: %s" % resp.text[:200]) from exc
