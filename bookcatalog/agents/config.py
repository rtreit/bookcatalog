"""Configuration for BookCatalog agents and MCP connections."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
PREPROCESSOR_MODEL: str = os.environ.get("PREPROCESSOR_MODEL", "gpt-5-nano")
VISION_MODEL: str = os.environ.get("VISION_MODEL", "gpt-4o")

# Path to the MCP server script (agents/ -> bookcatalog/ -> mcp/)
MCP_BOOK_SEARCH_PATH: str = str(
    Path(__file__).resolve().parent.parent / "mcp" / "book_search.py"
)

# uv executable for launching MCP servers as subprocesses
_UV_PATH = os.environ.get("UV_PATH", "uv")


def get_mcp_server_config() -> dict:
    """Return MCP server configuration for MultiServerMCPClient.

    Uses uv to run the MCP book search server so the project's
    virtual environment and dependencies are available.
    """
    return {
        "book_search": {
            "command": _UV_PATH,
            "args": ["run", "python", MCP_BOOK_SEARCH_PATH],
            "transport": "stdio",
        },
    }
