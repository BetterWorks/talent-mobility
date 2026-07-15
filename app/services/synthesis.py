import json
import re
from typing import List

from app import settings
from app.db.data_embeddings import DataEmbeddings
from app.models.candidate_profile_data import LLMCandidateInsights
from app.prompt.candidate_profile import build_candidate_profile_messages
from app.utils.llm_proxy import exec_llm_proxy


_JSON_FENCE = re.compile(r'```(?:json)?\s*(\{.*\})\s*```', re.DOTALL)


def _extract_json(content: str) -> dict:
    """Parse a JSON object from an LLM response, tolerating markdown fences or
    surrounding prose.
    """
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = _JSON_FENCE.search(content)
    if not match:
        # Fall back to the first balanced-looking {...} span.
        start, end = content.find('{'), content.rfind('}')
        if start == -1 or end == -1 or end <= start:
            raise ValueError('No JSON object found in LLM response')
        candidate = content[start:end + 1]
    else:
        candidate = match.group(1)
    return json.loads(candidate)


async def synthesize_candidate(
    job_description: str, rows: List[DataEmbeddings]
) -> LLMCandidateInsights:
    """Run one LLM call for a single candidate and return validated insights.

    Raises on empty response, unparseable JSON, or schema-invalid output; the
    caller decides whether to skip this candidate or fail the run.
    """
    messages = build_candidate_profile_messages(job_description, rows)
    completion = await exec_llm_proxy(
        model=settings.PRIVATE_LLM_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=4096,
    )

    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        raise ValueError('Empty LLM response for candidate synthesis')

    return LLMCandidateInsights.model_validate(_extract_json(content))
