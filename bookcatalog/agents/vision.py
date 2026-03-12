"""Vision agent for analyzing photos of book stacks.

Uses a vision-capable model via LangGraph with native local book tools to:
1. Identify book titles and authors from an image
2. Match each identified book against the local Open Library database
"""

import base64
import json
import logging
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

3. Use the match_book tool to look up each identified book and get accurate metadata.

4. Return your results as a JSON array. Each element must have:
   - "extracted_title": what you read from the image
   - "extracted_author": author if visible (null if not)
   - "matched_title": the matched title from the database (null if no match)
   - "matched_authors": list of matched author names (empty if no match)
   - "year": publication year if found (null otherwise)
   - "confidence": 0.0 to 1.0 confidence in the visual identification
   - "match_confidence": 0.0 to 1.0 confidence in the database match (null if no match)
   - "notes": any relevant notes (e.g., "partially obscured", "spine text only")

IMPORTANT:
- Always use the match_book tool for every book you identify.
- If you can only partially read a title, still try to match it.
- Note any books that are partially obscured or hard to read.
- Respond with ONLY the JSON array, no other text."""


async def run_vision_agent(
    image_data: bytes,
    media_type: str = "image/jpeg",
    tools: list | None = None,
) -> list[dict[str, Any]]:
    """Analyze a photo of books and match identified titles.

    Args:
        image_data: Raw image bytes.
        media_type: MIME type of the image (e.g., "image/jpeg", "image/png").
        tools: Optional pre-loaded tools (for testing).

    Returns:
        List of identified and matched books.
    """
    model = ChatOpenAI(
        model=VISION_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    if tools is None:
        tools = get_agent_tools()

    return await _invoke_vision_agent(model, tools, image_data, media_type)


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


async def _invoke_vision_agent(
    model: ChatOpenAI,
    tools: list,
    image_data: bytes,
    media_type: str,
) -> list[dict[str, Any]]:
    """Create and invoke the vision agent."""
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)

    b64_image = base64.b64encode(image_data).decode("utf-8")
    image_url = f"data:{media_type};base64,{b64_image}"

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
    })

    last_message = result["messages"][-1]
    content = (
        last_message.content
        if hasattr(last_message, "content")
        else str(last_message)
    )

    return _parse_vision_response(content)


def _parse_vision_response(content: str) -> list[dict[str, Any]]:
    """Parse the vision agent's JSON response."""
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
