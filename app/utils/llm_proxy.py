from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app import settings


async def exec_llm_proxy(model: str, messages: list, **kwargs) -> ChatCompletion:
    extra_headers = {
        "Authorization": "Token %s" % settings.LLM_PROXY_TOKEN,
    }
    client = AsyncOpenAI(base_url=settings.LLM_PROXY_URL, api_key=settings.OPENAI_API_KEY)
    return await client.chat.completions.create(
        messages=messages,
        model=model,
        temperature=kwargs.get('temperature'),
        max_tokens=kwargs.get('max_tokens'),
        extra_headers=extra_headers,
    )
