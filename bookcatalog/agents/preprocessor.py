"""Conversational book assistant backed by native local book tools."""

import json
import logging
import re
from typing import Any, TypedDict

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .config import OPENAI_API_KEY, PREPROCESSOR_MODEL
from .tools import get_agent_tools

logger = logging.getLogger(__name__)


class AssistantResponse(TypedDict):
    """Structured response returned by the conversational book assistant."""

    raw_response: str
    results: list[dict[str, Any]]


SYSTEM_PROMPT = """You are Book Assistant, a conversational librarian for a local book catalog.

You can:
- Answer questions about books, authors, genres, and reading suggestions.
- Search the local Open Library database with search_books when you need catalog facts.
- Use match_book when the user gives a specific title or item that may be a book.
- Use get_database_stats when it helps explain what is available in the local catalog.
- Hold natural multi-turn conversations and rely on the message history for follow-up questions.

Database scope:
- The local catalog indexes Open Library WORKS and EDITIONS.
- Work-level fields: title, authors, subtitle, first_publish_year, subjects, description,
  first_sentence, LC/Dewey classifications.
- Edition-level fields (via match_book): ISBN, publisher, page count, format, edition count.
- If edition data has not been loaded yet, match_book will still return work-level data
  but without ISBN/publisher/pages. Say so if edition fields are missing.

Efficiency rules:
- Make ONE tool call per book when possible. Do not retry the same query with
  minor variations.
- After a match_book or search_books call, use the returned data to answer.
  Do not re-search for the same title.

Behavior rules:
- For normal conversation, reply naturally in plain language.
- When the user pastes a list of items, especially one item per line, treat it as a classification task.
- For classification tasks, decide whether each item is a book or not a book.
- For anything you classify as a book or likely book, use match_book to verify and enrich the result.
- Product names with brand names, specs, or model numbers are usually not books.
- If search results are uncertain or missing, say so clearly.

When handling a list classification task:
1. Give a short conversational summary first.
2. Then include a JSON array in a ```json fenced block.
3. Each array item must include:
   - "input"
   - "is_book"
   - "title"
   - "authors"
   - "year"
   - "confidence"
   - "decision"
   - "reason"

For non-classification conversation, do not include JSON unless structured results would clearly help.
Do not invent tool results. Ground catalog-specific claims in the available tools when needed."""


async def run_preprocessor(
    items: list[str] | None = None,
    messages: list[dict[str, str]] | None = None,
    tools: list[Any] | None = None,
) -> AssistantResponse:
    """Run the conversational book assistant.

    Args:
        items: Optional legacy list of raw item strings to classify.
        messages: Optional chat history as a list of role/content dicts.
        tools: Optional pre-loaded tools, mainly for testing.

    Returns:
        A response containing the assistant's prose reply and any parsed
        structured classification results.
    """
    normalized_messages = _normalize_messages(items=items, messages=messages)

    model = ChatOpenAI(
        model=PREPROCESSOR_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    if tools is None:
        tools = get_agent_tools()

    return await _invoke_agent(model, tools, normalized_messages)


def _normalize_messages(
    items: list[str] | None = None,
    messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Normalize legacy item input or chat history into agent messages."""
    if messages:
        normalized_history: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user")).strip() or "user"
            content = str(message.get("content", "")).strip()
            if content:
                normalized_history.append({"role": role, "content": content})
        if normalized_history:
            return normalized_history

    cleaned_items = [item.strip() for item in items or [] if item.strip()]
    if not cleaned_items:
        raise ValueError("Either messages or items must contain at least one entry.")

    if len(cleaned_items) == 1:
        return [{"role": "user", "content": cleaned_items[0]}]

    list_content = "\n".join(cleaned_items)
    return [{
        "role": "user",
        "content": (
            "Please classify the following items, identify which are books, "
            "and match any books you can verify:\n\n"
            f"{list_content}"
        ),
    }]


async def _invoke_agent(
    model: ChatOpenAI,
    tools: list[Any],
    messages: list[dict[str, str]],
) -> AssistantResponse:
    """Create and invoke the assistant with the given tools and messages."""
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke(
        {"messages": messages},
        config={"recursion_limit": 12},
    )

    last_message = result["messages"][-1]
    content = _message_content_to_text(
        last_message.content if hasattr(last_message, "content") else last_message
    )
    raw_response = _extract_text_response(content)
    structured_payload = _extract_structured_payload(content)
    original_items = _extract_latest_user_items(messages)
    parsed_results = (
        _parse_response(structured_payload, original_items)
        if structured_payload is not None
        else []
    )

    return {
        "raw_response": raw_response,
        "results": parsed_results,
    }


def _message_content_to_text(content: Any) -> str:
    """Convert LangChain message content into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)

    return str(content)


def _extract_latest_user_items(messages: list[dict[str, str]]) -> list[str]:
    """Extract likely list items from the most recent user message."""
    for message in reversed(messages):
        if message.get("role") != "user":
            continue

        content = message.get("content", "").strip()
        if not content:
            return []

        lines = [line.strip(" -\t") for line in content.splitlines()]
        non_empty_lines = [line for line in lines if line]
        if len(non_empty_lines) <= 1:
            return non_empty_lines

        if non_empty_lines[0].lower().startswith("please classify"):
            return non_empty_lines[1:]
        return non_empty_lines

    return []


def _extract_structured_payload(content: str) -> str | None:
    """Extract a JSON array payload from an assistant response, if present."""
    text = content.strip()
    if not text:
        return None

    fenced_match = re.search(
        r"```(?:json)?\s*(\[[\s\S]*?\])\s*```",
        text,
        flags=re.IGNORECASE,
    )
    if fenced_match:
        return fenced_match.group(1).strip()

    full_text = text.strip()
    if full_text.startswith("[") and full_text.endswith("]"):
        return full_text

    bracket_match = re.search(r"(\[[\s\S]*\])", text)
    if bracket_match:
        return bracket_match.group(1).strip()

    return None


def _extract_text_response(content: str) -> str:
    """Remove structured JSON blocks so the chat UI can show assistant prose."""
    text = re.sub(
        r"```(?:json)?\s*\[[\s\S]*?\]\s*```",
        "",
        content,
        flags=re.IGNORECASE,
    ).strip()
    return text


def _parse_response(
    content: str, original_items: list[str]
) -> list[dict[str, Any]]:
    """Parse the agent's JSON response into structured results."""
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
        logger.warning("Failed to parse agent response as JSON: %s", text[:200])

    return [
        {
            "input": item,
            "is_book": None,
            "title": None,
            "authors": [],
            "year": None,
            "confidence": 0.0,
            "decision": "error",
            "reason": "Failed to parse agent response",
        }
        for item in original_items
    ]
