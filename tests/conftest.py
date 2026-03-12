"""Test configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars for tests unless already present."""
    monkeypatch.setenv("PREPROCESSOR_MODEL", "gpt-5-nano")
    monkeypatch.setenv("VISION_MODEL", "gpt-4o")
