"""Preprocessor agent for classifying and matching book titles.

Uses gpt-5-nano via LangGraph with the book search MCP tool to:
1. Classify items as book or non-book
2. Extract clean title and author from book items
3. Match books against the local Open Library database
"""

import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from .config import OPENAI_API_KEY, PREPROCESSOR_MODEL, get_mcp_server_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a book classification and matching assistant.

Your job is to process a list of items and determine which ones are real books.
For each item:

1. Decide if it is a BOOK or NOT A BOOK.
   - Books include novels, textbooks, manuals, cookbooks, and any published written work.
   - Non-books include electronics, accessories, hardware, household items, software,
     and any other consumer product that is not a published book.

2. For items that ARE books, use the match_book tool to look up the book and get
   accurate metadata (title, author, publication year).

3. Return your results as a JSON array. Each element must have these fields:
   - "input": the original input string
   - "is_book": true or false
   - "title": the matched/cleaned book title (null if not a book)
   - "authors": list of author names (empty list if not a book)
   - "year": publication year as integer (null if unknown or not a book)
   - "confidence": a number from 0.0 to 1.0 indicating your confidence
   - "decision": "book", "likely_book", or "not_a_book"
   - "reason": brief explanation of your classification

IMPORTANT:
- Always use the match_book tool for items you classify as books.
- Product names with brand names, model numbers, specs (GB, mAh, Hz) are NOT books.
- Be decisive - if something is clearly a consumer product, classify it as not_a_book
  without searching for it.
- Respond with ONLY the JSON array, no other text."""


async def run_preprocessor(
    items: list[str],
    tools: list | None = None,
) -> list[dict[str, Any]]:
    """Run the preprocessor agent on a list of items.

    Args:
        items: Raw input strings to classify and match.
        tools: Optional pre-loaded tools (for testing). If None, tools are
            loaded from the MCP book search server.

    Returns:
        List of classification results with match metadata.
    """
    model = ChatOpenAI(
        model=PREPROCESSOR_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    if tools is None:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(get_mcp_server_config())
        mcp_tools = await client.get_tools()
        return await _invoke_agent(model, mcp_tools, items)
    else:
        return await _invoke_agent(model, tools, items)


async def _invoke_agent(
    model: ChatOpenAI,
    tools: list,
    items: list[str],
) -> list[dict[str, Any]]:
    """Create and invoke the agent with the given tools."""
    agent = create_react_agent(model, tools)

    items_text = "\n".join(f"- {item}" for item in items)
    user_message = f"Classify and match the following items:\n\n{items_text}"

    result = await agent.ainvoke({
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    })

    last_message = result["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

    return _parse_response(content, items)


def _parse_response(
    content: str, original_items: list[str]
) -> list[dict[str, Any]]:
    """Parse the agent's JSON response into structured results."""
    # Strip markdown code fences if present
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
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

    # Fallback: return items as unclassified
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
