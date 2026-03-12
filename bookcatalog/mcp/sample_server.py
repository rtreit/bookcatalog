"""Sample MCP server for demonstration and testing.

Provides simple utility tools to validate that agent-MCP wiring works.

Usage:
    uv run python -m bookcatalog.mcp.sample_server
"""

import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SampleTools")


@mcp.tool()
def get_current_time() -> str:
    """Get the current date and time.

    Returns:
        The current timestamp in ISO 8601 format.
    """
    return datetime.datetime.now().isoformat()


@mcp.tool()
def word_count(text: str) -> str:
    """Count the number of words in the given text.

    Args:
        text: The text to count words in.

    Returns:
        The word count as a string.
    """
    count = len(text.split())
    return f"{count} words"


@mcp.tool()
def reverse_text(text: str) -> str:
    """Reverse the given text.

    Args:
        text: The text to reverse.

    Returns:
        The reversed text.
    """
    return text[::-1]


if __name__ == "__main__":
    mcp.run(transport="stdio")
