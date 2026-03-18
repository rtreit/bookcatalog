"""Vision agent for analyzing photos of book stacks.

Uses a vision-capable model via LangGraph with native local book tools to:
1. Identify book titles and authors from an image
2. Match each identified book against the local Open Library database
"""

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .config import OPENAI_API_KEY, VISION_MODEL
from .tools import get_agent_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a book identification assistant with computer vision.

You will receive an image of one or more books (a shelf, a stack, a pile, a single
book, etc.). Your job is to:

1. Examine the image carefully and identify every book visible.
   Look at spines, covers, and any visible text.

2. For each book you can identify, extract:
   - The title (as best you can read it)
   - The author (if visible)

3. Use the match_book tool to look up each identified book. Always pass the author
   parameter when you can read or infer the author from the image - this greatly
   improves match accuracy.

4. Validate each match before including it:
   - If the matched authors do not match the author you read from the image, the
     match is likely wrong. Set match_confidence to 0.0 and note the mismatch.
   - If the matched title is substantially different from what you read, lower
     the match_confidence accordingly.
   - Use your judgment: minor differences (e.g., "A" vs "The", subtitle added)
     are acceptable. Completely different authors are not.

5. Return your results as a JSON array. Each element must have:
   - "extracted_title": what you read from the image
   - "extracted_author": author if visible (null if not)
   - "matched_title": the matched title from the database (null if no match)
   - "work_key": the matched Open Library work key (null if no match)
   - "matched_authors": list of matched author names (empty if no match)
   - "year": publication year if found (null otherwise)
   - "confidence": 0.0 to 1.0 confidence in the visual identification
   - "match_confidence": 0.0 to 1.0 confidence in the database match (null if no match)
   - "notes": any relevant notes (e.g., "partially obscured", "spine text only")

IMPORTANT:
- Always use the match_book tool for every book you identify.
- Always pass the author parameter to match_book when you can see or infer the author.
- When match_book returns a work key, copy that exact work_key into your JSON.
- If you can only partially read a title, still try to match it.
- Note any books that are partially obscured or hard to read.
- Respond with ONLY the JSON array, no other text."""


async def run_vision_agent(
    image_data: bytes,
    media_type: str = "image/jpeg",
    tools: list | None = None,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
) -> list[dict[str, Any]]:
    """Analyze a photo of books and match identified titles.

    Args:
        image_data: Raw image bytes.
        media_type: MIME type of the image (e.g., "image/jpeg", "image/png").
        tools: Optional pre-loaded tools (for testing).
        model_name: Optional model override for benchmarking.
        reasoning_effort: Optional GPT-5 reasoning effort override.
        verbosity: Optional GPT-5 verbosity override.

    Returns:
        List of identified and matched books.
    """
    details = await run_vision_agent_detailed(
        image_data=image_data,
        media_type=media_type,
        tools=tools,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )
    if isinstance(details, list):
        return details
    return details["books"]

async def run_vision_agent_detailed(
    image_data: bytes,
    media_type: str = "image/jpeg",
    tools: list | None = None,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
) -> dict[str, Any]:
    """Analyze a photo and return parsed books plus raw diagnostics."""
    model = _build_vision_model(
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )

    if tools is None:
        tools = get_agent_tools()

    details = await _invoke_vision_agent(model, tools, image_data, media_type)
    if isinstance(details, list):
        return {
            "books": details,
            "raw_response": "",
            "elapsed_ms": 0.0,
            "usage": [],
            "model": str(model_name or VISION_MODEL),
        }
    return details


async def analyze_photo_file(
    file_path: str | Path,
    tools: list | None = None,
) -> list[dict[str, Any]]:
    """Analyze a photo file of books.

    Args:
        file_path: Path to the image file.
        tools: Optional pre-loaded tools (for testing).

    Returns:
        List of identified and matched books.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/jpeg")

    return await run_vision_agent(path.read_bytes(), media_type, tools)


def _build_vision_model(
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
) -> ChatOpenAI:
    """Create the configured vision model."""
    kwargs: dict[str, Any] = {
        "model": model_name or VISION_MODEL,
        "api_key": OPENAI_API_KEY,
        "temperature": 0,
    }
    if reasoning_effort:
        kwargs["reasoning"] = {"effort": reasoning_effort}
    if verbosity:
        kwargs["verbosity"] = verbosity
    return ChatOpenAI(**kwargs)


def _message_content_to_text(content: Any) -> str:
    """Convert LangChain message content into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(part for part in parts if part)

    return str(content)


def _extract_final_ai_text(messages: list[Any]) -> str:
    """Find the final AI text response from an agent run."""
    for message in reversed(messages):
        if getattr(message, "type", None) != "ai":
            continue
        text = _message_content_to_text(getattr(message, "content", None)).strip()
        if text:
            return text

    if not messages:
        return ""
    last_message = messages[-1]
    return _message_content_to_text(
        getattr(last_message, "content", last_message)
    ).strip()


def _normalize_usage_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize usage metadata across ChatOpenAI response formats."""
    if "input_tokens" in payload:
        return {
            "input_tokens": int(payload.get("input_tokens", 0) or 0),
            "output_tokens": int(payload.get("output_tokens", 0) or 0),
            "total_tokens": int(payload.get("total_tokens", 0) or 0),
            "input_token_details": dict(payload.get("input_token_details") or {}),
            "output_token_details": dict(payload.get("output_token_details") or {}),
        }

    prompt_details = dict(payload.get("prompt_tokens_details") or {})
    completion_details = dict(payload.get("completion_tokens_details") or {})
    return {
        "input_tokens": int(payload.get("prompt_tokens", 0) or 0),
        "output_tokens": int(payload.get("completion_tokens", 0) or 0),
        "total_tokens": int(payload.get("total_tokens", 0) or 0),
        "input_token_details": {
            "audio": int(prompt_details.get("audio_tokens", 0) or 0),
            "cache_read": int(prompt_details.get("cached_tokens", 0) or 0),
        },
        "output_token_details": {
            "audio": int(completion_details.get("audio_tokens", 0) or 0),
            "reasoning": int(completion_details.get("reasoning_tokens", 0) or 0),
        },
    }


def _extract_usage_records(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract normalized usage metadata from AI messages."""
    usage_records: list[dict[str, Any]] = []
    for message in messages:
        if getattr(message, "type", None) != "ai":
            continue
        usage = getattr(message, "usage_metadata", None)
        if usage:
            usage_records.append(_normalize_usage_record(dict(usage)))
            continue
        response_metadata = getattr(message, "response_metadata", None) or {}
        token_usage = response_metadata.get("token_usage")
        if token_usage:
            usage_records.append(_normalize_usage_record(dict(token_usage)))
    return usage_records


def _extract_model_name(messages: list[Any], fallback: str) -> str:
    """Extract the concrete model snapshot used by the API."""
    for message in messages:
        response_metadata = getattr(message, "response_metadata", None) or {}
        model_name = response_metadata.get("model_name")
        if model_name:
            return str(model_name)
    return fallback


async def _invoke_vision_agent(
    model: ChatOpenAI,
    tools: list,
    image_data: bytes,
    media_type: str,
) -> dict[str, Any]:
    """Create and invoke the vision agent with diagnostics."""
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)

    b64_image = base64.b64encode(image_data).decode("utf-8")
    image_url = f"data:{media_type};base64,{b64_image}"

    t0 = time.perf_counter()
    result = await agent.ainvoke({
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Please identify all the books in this image "
                            "and look up each one."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ],
    }, config={"recursion_limit": 20})
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    messages = result["messages"]
    content = _extract_final_ai_text(messages)
    usage_records = _extract_usage_records(messages)
    resolved_model = _extract_model_name(
        messages,
        str(getattr(model, "model_name", None) or getattr(model, "model", VISION_MODEL)),
    )

    if not content:
        logger.warning("Vision agent returned no text content")
        books = [
            {
                "extracted_title": None,
                "error": "Vision agent did not return a text response",
                "raw_response": str(messages[-1])[:500] if messages else "",
            }
        ]
        return {
            "books": books,
            "raw_response": "",
            "elapsed_ms": elapsed_ms,
            "usage": usage_records,
            "model": resolved_model,
        }

    return {
        "books": _parse_vision_response(content),
        "raw_response": content,
        "elapsed_ms": elapsed_ms,
        "usage": usage_records,
        "model": resolved_model,
    }


def _parse_vision_response(content: str | None) -> list[dict[str, Any]]:
    """Parse the vision agent's JSON response."""
    if not content:
        return [
            {
                "extracted_title": None,
                "error": "Empty response from vision agent",
                "raw_response": "",
            }
        ]

    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse vision response as JSON: %s", text[:200])

    return [
        {
            "extracted_title": None,
            "error": "Failed to parse vision agent response",
            "raw_response": content[:500],
        }
    ]
