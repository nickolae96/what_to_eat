"""LLM client for decomposing free-text meal descriptions."""

import json
import logging
import re

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

SYSTEM_PROMPT = """
Extract foods from the user's message.

Return ONLY a JSON array.

Each item must follow this schema:
{"food_name": string, "quantity_g": float, "meal_type": "breakfast|lunch|dinner|snack|null"}

Estimate portions when unclear:
plate of rice = 250g
glass of milk = 250g
chicken breast = 150g

Example:
Input: grilled chicken breast with rice and salad for lunch
Output:
[{"food_name":"grilled chicken breast","quantity_g":150.0,"meal_type":"lunch"},
{"food_name":"white rice","quantity_g":250.0,"meal_type":"lunch"},
{"food_name":"mixed green salad","quantity_g":100.0,"meal_type":"lunch"}]
"""


class ParsedFoodItem(BaseModel):
    food_name: str
    quantity_g: float
    meal_type: str | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_url)
    return _client


def _sanitize_unicode_json(text: str) -> str:
    """
    Replace common Unicode look-alikes that LLMs produce with their
    ASCII equivalents so ``json.loads`` can handle the string.
    """
    replacements = {
        # Fullwidth brackets / braces
        "\uff3b": "[",   # ［
        "\uff3d": "]",   # ］
        "\uff5b": "{",   # ｛
        "\uff5d": "}",   # ｝
        # Smart / curly double quotes
        "\u201c": '"',   # "
        "\u201d": '"',   # "
        "\u201e": '"',   # „
        # Smart / curly single quotes
        "\u2018": "'",   # '
        "\u2019": "'",   # '
        # Fullwidth colon / comma
        "\uff1a": ":",   # ：
        "\uff0c": ",",   # ，
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _coerce_to_list(result: object) -> list:
    """Turn a parsed JSON value into a list of food-item dicts, or raise."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for value in result.values():
            if isinstance(value, list):
                return value
        if "food_name" in result:
            return [result]
    raise ValueError("Parsed JSON is neither a list nor a recognised object shape")


def _extract_json_array(raw: str) -> list:
    """
    Extract the first JSON array from *raw*, ignoring any preamble text,
    markdown fences, or trailing commentary the LLM may have added.

    Strategy:
      0. Sanitize Unicode look-alike characters.
      1. Try ``json.loads`` on the full string (fast path).
      2. Look for a ``[…]`` substring using bracket-depth counting so we
         handle nested objects correctly.
      3. As a last resort, try a regex that grabs everything between the
         first ``[`` and the last ``]``.
    """
    raw = _sanitize_unicode_json(raw.strip())

    # Fast path — the response is already clean JSON
    try:
        result = json.loads(raw)
        return _coerce_to_list(result)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strip markdown fences (```json … ```)
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    # Bracket-depth scan: find the first balanced [...] or {...}
    start = None
    open_char = None
    close_char = None
    for idx, ch in enumerate(raw):
        if ch in ("[", "{"):
            start = idx
            open_char = ch
            close_char = "]" if ch == "[" else "}"
            break

    if start is not None:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == open_char:
                depth += 1
            elif raw[i] == close_char:
                depth -= 1
                if depth == 0:
                    candidate = raw[start : i + 1]
                    try:
                        result = json.loads(candidate)
                        return _coerce_to_list(result)
                    except (json.JSONDecodeError, ValueError):
                        break

    # Last resort: grab everything between first [ and last ]
    first_bracket = raw.find("[")
    last_bracket = raw.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidate = raw[first_bracket : last_bracket + 1]
        try:
            result = json.loads(candidate)
            return _coerce_to_list(result)
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"Could not extract a JSON array from LLM response: {raw[:200]}")


async def decompose_meal_text(text: str) -> list[ParsedFoodItem]:
    """Send *text* to the configured LLM and return structured food items."""
    client = _get_client()

    kwargs: dict = dict(
        model=settings.llm_model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        temperature=0,
        top_p=0.9
    )

    response = await client.chat.completions.create(**kwargs)

    raw = response.choices[0].message.content or "[]"
    logger.debug("LLM raw response: %s", raw)

    items = _extract_json_array(raw)

    return [ParsedFoodItem.model_validate(item) for item in items]

