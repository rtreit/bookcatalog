"""Tests for the agent configuration module."""

import os

import pytest

from bookcatalog.agents.config import (
    MCP_BOOK_SEARCH_PATH,
    get_mcp_server_config,
)


class TestConfig:
    """Tests for agent configuration."""

    def test_mcp_book_search_path_exists(self) -> None:
        """The MCP book search server script path is valid."""
        assert os.path.isfile(MCP_BOOK_SEARCH_PATH)

    def test_get_mcp_server_config_structure(self) -> None:
        """MCP server config has the expected structure."""
        config = get_mcp_server_config()
        assert "book_search" in config
        bs = config["book_search"]
        assert "command" in bs
        assert "args" in bs
        assert "transport" in bs
        assert bs["transport"] == "stdio"

    def test_mcp_server_config_args_include_server_path(self) -> None:
        """MCP server config args include the book search server path."""
        config = get_mcp_server_config()
        args = config["book_search"]["args"]
        assert any("book_search" in str(a) for a in args)
