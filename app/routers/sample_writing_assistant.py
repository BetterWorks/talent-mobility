"""Standalone sample endpoint to sanity-check the llm-proxy connection.

Not wired into any business flow — hits `exec_llm_proxy` with a hardcoded
system prompt + the caller's user prompt, mirroring llm-engine's
GPT3Handler.get_prompt()/generate_response() shape in its simplest form.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.settings import PRIVATE_LLM_MODEL
from app.utils.llm_proxy import exec_llm_proxy


router = APIRouter(prefix="/api/sample/writing-assistant", tags=["sample"])

SYSTEM_PROMPT = "You are a helpful writing assistant. Keep responses concise and professional."


class SampleWritingAssistantRequest(BaseModel):
    prompt: str


class SampleWritingAssistantResponse(BaseModel):
    output: str


@router.post("/", response_model=SampleWritingAssistantResponse)
async def generate_sample_response(payload: SampleWritingAssistantRequest):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": payload.prompt},
    ]
    completion = await exec_llm_proxy(model=PRIVATE_LLM_MODEL, messages=messages)
    return SampleWritingAssistantResponse(output=completion.choices[0].message.content)
