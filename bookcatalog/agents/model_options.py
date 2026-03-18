"""Shared model picker options for the frontend dashboard."""

from __future__ import annotations

from typing import Any

from .config import PREPROCESSOR_MODEL, VISION_MODEL

_CHAT_MODELS: list[dict[str, str]] = [
    {
        "value": "gpt-5-nano",
        "label": "GPT-5 nano",
        "description": "Fastest and cheapest chat option. Current configured default.",
    },
    {
        "value": "gpt-5-mini",
        "label": "GPT-5 mini",
        "description": "Balanced GPT-5 option for faster chat responses.",
    },
    {
        "value": "gpt-5",
        "label": "GPT-5",
        "description": "Higher quality chat model with stronger reasoning.",
    },
    {
        "value": "gpt-5.4",
        "label": "GPT-5.4",
        "description": "Highest quality GPT-5 tier, usually slower and more expensive.",
    },
    {
        "value": "gpt-4.1-mini",
        "label": "GPT-4.1 mini",
        "description": "Lower-cost GPT-4.1 option for lightweight chat.",
    },
    {
        "value": "gpt-4.1",
        "label": "GPT-4.1",
        "description": "Reliable general-purpose model.",
    },
]

_VISION_MODELS: list[dict[str, str]] = [
    {
        "value": "gpt-4.1",
        "label": "GPT-4.1",
        "description": "Current vision default. Best reliability/cost tradeoff so far.",
    },
    {
        "value": "gpt-5",
        "label": "GPT-5",
        "description": "Can perform well on photo matching, but recent benchmark was slower and less reliable than GPT-4.1.",
    },
    {
        "value": "gpt-5.4",
        "label": "GPT-5.4",
        "description": "Strong photo accuracy, typically slower and more expensive than GPT-4.1.",
    },
    {
        "value": "gpt-5-mini",
        "label": "GPT-5 mini",
        "description": "Lower-cost GPT-5 option for experimentation.",
    },
    {
        "value": "gpt-5-nano",
        "label": "GPT-5 nano",
        "description": "Very cheap and fast, but benchmarked poorly for photo import.",
    },
]


def _ensure_model_present(
    configured_model: str,
    options: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Ensure the configured environment model appears in the picker list."""
    if any(option["value"] == configured_model for option in options):
        return [dict(option) for option in options]

    return [
        {
            "value": configured_model,
            "label": configured_model,
            "description": "Configured through environment variables.",
        },
        *[dict(option) for option in options],
    ]


def get_model_picker_options() -> dict[str, Any]:
    """Return shared model picker metadata for chat and vision pages."""
    return {
        "chat": {
            "default_model": PREPROCESSOR_MODEL,
            "options": _ensure_model_present(PREPROCESSOR_MODEL, _CHAT_MODELS),
        },
        "vision": {
            "default_model": VISION_MODEL,
            "options": _ensure_model_present(VISION_MODEL, _VISION_MODELS),
        },
    }
