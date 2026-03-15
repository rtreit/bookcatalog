"""Benchmark helpers for photo-analysis models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bookcatalog.research import normalize_title

from .vision import run_vision_agent_detailed

_BENCHMARK_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "benchmarks"
)

_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
}

_BENCHMARK_MODELS: list[dict[str, Any]] = [
    {
        "model": "gpt-4.1",
        "label": "GPT-4.1 (current default)",
        "selected": True,
        "reasoning_options": [],
        "verbosity_options": [],
        "pricing": _MODEL_PRICING["gpt-4.1"],
    },
    {
        "model": "gpt-5.4",
        "label": "GPT-5.4",
        "selected": True,
        "reasoning_effort": "none",
        "verbosity": "low",
        "reasoning_options": ["none", "low", "medium", "high", "xhigh"],
        "verbosity_options": ["low", "medium", "high"],
        "pricing": _MODEL_PRICING["gpt-5.4"],
    },
    {
        "model": "gpt-5-nano",
        "label": "GPT-5 nano",
        "selected": True,
        "reasoning_effort": "minimal",
        "verbosity": "low",
        "reasoning_options": ["minimal", "low", "medium", "high"],
        "verbosity_options": ["low", "medium", "high"],
        "pricing": _MODEL_PRICING["gpt-5-nano"],
    },
    {
        "model": "gpt-5",
        "label": "GPT-5",
        "selected": False,
        "reasoning_effort": "minimal",
        "verbosity": "low",
        "reasoning_options": ["minimal", "low", "medium", "high"],
        "verbosity_options": ["low", "medium", "high"],
        "pricing": _MODEL_PRICING["gpt-5"],
    },
]

_BENCHMARK_CASES: dict[str, dict[str, Any]] = {
    "8-books-shelf": {
        "id": "8-books-shelf",
        "name": "8 Books Shelf",
        "description": (
            "Eight visible books on a shelf. Includes exact spine reads, "
            "author inference, and one recent title that previously missed."
        ),
        "image_path": _BENCHMARK_DATA_DIR / "8-books.jpg",
        "expected_books": [
            {
                "label": "The Oxford Companion to Philosophy",
                "extracted_aliases": [
                    "The Oxford Companion to Philosophy",
                ],
                "matched_aliases": [
                    "The Oxford Companion to Philosophy",
                    "The Oxford companion to philosophy",
                ],
                "author_aliases": ["Ted Honderich", "Honderich"],
                "must_match": True,
            },
            {
                "label": "Jo's Boys",
                "extracted_aliases": ["Jo's Boys", "Jos Boys"],
                "matched_aliases": ["Jo's Boys", "Jos Boys"],
                "author_aliases": ["Louisa May Alcott", "Alcott"],
                "must_match": True,
            },
            {
                "label": "The Stillmeadow Road",
                "extracted_aliases": ["The Stillmeadow Road"],
                "matched_aliases": ["The Stillmeadow Road", "The Stillmeadow road"],
                "author_aliases": [
                    "Gladys Bagg Taber",
                    "Gladys Taber",
                    "Taber",
                ],
                "must_match": True,
            },
            {
                "label": "The Secret Book of Flora Lea",
                "extracted_aliases": [
                    "The Secret Book of Flora Lea",
                    "Secret Book of Flora Lea",
                ],
                "matched_aliases": [
                    "The Secret Book of Flora Lea",
                    "Secret Book of Flora Lea",
                ],
                "author_aliases": ["Patti Callahan Henry"],
                "must_match": True,
            },
            {
                "label": "Edgar Allan Poe collection",
                "extracted_aliases": [
                    "Edgar Allan Poe",
                    "Great Works of Edgar Allan Poe",
                    "The Complete Tales and Poems of Edgar Allan Poe",
                ],
                "matched_aliases": [
                    "The complete tales and poems of Edgar Allan Poe",
                    "Great Short Works of Edgar Allan Poe",
                    "Edgar Allan Poe",
                ],
                "author_aliases": ["Edgar Allan Poe"],
                "must_match": True,
            },
            {
                "label": "The City of God",
                "extracted_aliases": ["The City of God", "City of God"],
                "matched_aliases": ["The City of God", "The city of God", "City of God"],
                "author_aliases": ["Saint Augustine", "Augustine"],
                "must_match": True,
            },
            {
                "label": "A Listening Walk",
                "extracted_aliases": ["A Listening Walk"],
                "matched_aliases": [
                    "A Listening Walk",
                    "A listening walk --and other stories",
                    "A listening walk and other stories",
                ],
                "author_aliases": ["Gene Hill"],
                "must_match": True,
            },
            {
                "label": "Bertrand Russell",
                "extracted_aliases": ["Bertrand Russell"],
                "matched_aliases": ["Bertrand Russell"],
                "author_aliases": ["Ray Monk", "Monk"],
                "must_match": True,
            },
        ],
    },
}


def _strip_leading_article(text: str) -> str:
    """Remove a leading article for benchmark title matching."""
    for prefix in ("a ", "an ", "the "):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _canonical_text(text: str | None) -> str:
    """Normalize text for benchmark comparisons."""
    if not text:
        return ""
    normalized = normalize_title(text)
    normalized = normalized.replace(" -- ", " ")
    normalized = normalized.replace("--", " ")
    normalized = " ".join(normalized.split())
    return normalized


def _alias_set(values: list[str]) -> set[str]:
    """Build normalized title aliases, including articleless variants."""
    aliases: set[str] = set()
    for value in values:
        canonical = _canonical_text(value)
        if not canonical:
            continue
        aliases.add(canonical)
        stripped = _strip_leading_article(canonical)
        if stripped and stripped != canonical:
            aliases.add(stripped)
    return aliases


def _prediction_title_aliases(book: dict[str, Any]) -> set[str]:
    """Return normalized title aliases from a prediction."""
    aliases: set[str] = set()
    for value in [book.get("extracted_title"), book.get("matched_title")]:
        canonical = _canonical_text(str(value) if value is not None else None)
        if not canonical:
            continue
        aliases.add(canonical)
        stripped = _strip_leading_article(canonical)
        if stripped and stripped != canonical:
            aliases.add(stripped)
    return aliases


def _prediction_match_aliases(book: dict[str, Any]) -> set[str]:
    """Return normalized aliases for only the matched DB title."""
    matched_title = book.get("matched_title")
    if matched_title is None:
        return set()
    return _alias_set([str(matched_title)])


def _prediction_author_aliases(book: dict[str, Any]) -> set[str]:
    """Return normalized author aliases from extracted and matched authors."""
    aliases: set[str] = set()
    extracted_author = book.get("extracted_author")
    if extracted_author:
        aliases.add(_canonical_text(str(extracted_author)))
    for author in book.get("matched_authors") or []:
        aliases.add(_canonical_text(str(author)))
    return {alias for alias in aliases if alias}


def _summarize_usage(usage_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate token usage across all AI turns in a run."""
    input_tokens = sum(int(record.get("input_tokens", 0) or 0) for record in usage_records)
    output_tokens = sum(int(record.get("output_tokens", 0) or 0) for record in usage_records)
    total_tokens = sum(int(record.get("total_tokens", 0) or 0) for record in usage_records)
    cached_input_tokens = sum(
        int((record.get("input_token_details") or {}).get("cache_read", 0) or 0)
        for record in usage_records
    )
    reasoning_tokens = sum(
        int((record.get("output_token_details") or {}).get("reasoning", 0) or 0)
        for record in usage_records
    )
    return {
        "calls": len(usage_records),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "billable_input_tokens": max(input_tokens - cached_input_tokens, 0),
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "records": usage_records,
    }


def _resolve_pricing(model_name: str) -> tuple[str | None, dict[str, float] | None]:
    """Resolve a pricing entry for an alias or snapshot model name."""
    for key in sorted(_MODEL_PRICING, key=len, reverse=True):
        if model_name == key or model_name.startswith(f"{key}-"):
            return key, _MODEL_PRICING[key]
    return None, None


def _estimate_cost(model_name: str, usage_summary: dict[str, Any]) -> dict[str, Any]:
    """Estimate run cost from token usage and static pricing."""
    pricing_model, pricing = _resolve_pricing(model_name)
    if pricing is None:
        return {
            "pricing_model": None,
            "estimated_total_cost_usd": None,
        }

    billable_input_tokens = int(usage_summary.get("billable_input_tokens", 0) or 0)
    cached_input_tokens = int(usage_summary.get("cached_input_tokens", 0) or 0)
    output_tokens = int(usage_summary.get("output_tokens", 0) or 0)

    input_cost = (billable_input_tokens / 1_000_000) * pricing["input"]
    cached_input_cost = (cached_input_tokens / 1_000_000) * pricing["cached_input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + cached_input_cost + output_cost

    return {
        "pricing_model": pricing_model,
        "input_rate_per_million": pricing["input"],
        "cached_input_rate_per_million": pricing["cached_input"],
        "output_rate_per_million": pricing["output"],
        "estimated_input_cost_usd": round(input_cost, 6),
        "estimated_cached_input_cost_usd": round(cached_input_cost, 6),
        "estimated_output_cost_usd": round(output_cost, 6),
        "estimated_total_cost_usd": round(total_cost, 6),
    }


def _evaluate_case(case: dict[str, Any], books: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare predicted books against a benchmark case's expectations."""
    expected_books = list(case["expected_books"])
    unused_predictions = list(range(len(books)))
    per_book: list[dict[str, Any]] = []
    identified_count = 0
    matched_count = 0
    author_count = 0

    for expected in expected_books:
        title_aliases = _alias_set(
            list(expected["extracted_aliases"]) + list(expected["matched_aliases"])
        )
        predicted_index: int | None = None
        for index in unused_predictions:
            if _prediction_title_aliases(books[index]) & title_aliases:
                predicted_index = index
                break

        if predicted_index is None:
            per_book.append({
                "label": expected["label"],
                "visual_ok": False,
                "match_ok": False,
                "author_ok": False,
                "prediction": None,
            })
            continue

        unused_predictions.remove(predicted_index)
        prediction = books[predicted_index]
        identified_count += 1

        match_ok = bool(
            _prediction_match_aliases(prediction)
            & _alias_set(list(expected["matched_aliases"]))
        )
        if match_ok:
            matched_count += 1

        author_aliases = _alias_set(list(expected.get("author_aliases", [])))
        author_ok = not author_aliases or bool(
            _prediction_author_aliases(prediction) & author_aliases
        )
        if author_ok:
            author_count += 1

        per_book.append({
            "label": expected["label"],
            "visual_ok": True,
            "match_ok": match_ok,
            "author_ok": author_ok,
            "prediction": {
                "extracted_title": prediction.get("extracted_title"),
                "extracted_author": prediction.get("extracted_author"),
                "matched_title": prediction.get("matched_title"),
                "matched_authors": prediction.get("matched_authors", []),
                "notes": prediction.get("notes", ""),
            },
        })

    unexpected_predictions = [
        {
            "extracted_title": books[index].get("extracted_title"),
            "matched_title": books[index].get("matched_title"),
            "notes": books[index].get("notes", ""),
        }
        for index in unused_predictions
    ]

    expected_count = len(expected_books)
    overall_score = round(
        ((identified_count + matched_count) / max(expected_count * 2, 1)),
        4,
    )

    return {
        "expected_count": expected_count,
        "predicted_count": len(books),
        "identified_count": identified_count,
        "matched_count": matched_count,
        "author_count": author_count,
        "overall_score": overall_score,
        "missed_labels": [
            item["label"] for item in per_book if not item["visual_ok"]
        ],
        "mismatch_labels": [
            item["label"] for item in per_book if item["visual_ok"] and not item["match_ok"]
        ],
        "per_book": per_book,
        "unexpected_predictions": unexpected_predictions,
    }


def list_benchmark_cases() -> dict[str, Any]:
    """Return available photo benchmark cases and recommended model configs."""
    cases: list[dict[str, Any]] = []
    for case in _BENCHMARK_CASES.values():
        cases.append({
            "id": case["id"],
            "name": case["name"],
            "description": case["description"],
            "image_path": str(case["image_path"]),
            "expected_books": case["expected_books"],
        })

    return {
        "cases": cases,
        "models": _BENCHMARK_MODELS,
        "pricing_source": "OpenAI pricing page snapshot as of 2026-03-15",
    }


async def run_photo_benchmark(
    case_id: str,
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run one photo benchmark case across a set of models."""
    case = _BENCHMARK_CASES.get(case_id)
    if case is None:
        raise ValueError(f"Unknown benchmark case: {case_id}")

    image_path = Path(case["image_path"])
    if not image_path.exists():
        raise FileNotFoundError(f"Benchmark image not found: {image_path}")

    image_data = image_path.read_bytes()
    runs: list[dict[str, Any]] = []
    for model_config in models:
        requested_model = str(model_config["model"])
        reasoning_effort = model_config.get("reasoning_effort")
        verbosity = model_config.get("verbosity")
        try:
            details = await run_vision_agent_detailed(
                image_data=image_data,
                media_type="image/jpeg",
                model_name=requested_model,
                reasoning_effort=(
                    str(reasoning_effort) if reasoning_effort is not None else None
                ),
                verbosity=str(verbosity) if verbosity is not None else None,
            )
            usage_summary = _summarize_usage(list(details.get("usage", [])))
            resolved_model = str(details.get("model") or requested_model)
            runs.append({
                "requested_model": requested_model,
                "resolved_model": resolved_model,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
                "elapsed_ms": float(details.get("elapsed_ms", 0.0) or 0.0),
                "usage": usage_summary,
                "cost": _estimate_cost(resolved_model, usage_summary),
                "books": details.get("books", []),
                "raw_response": str(details.get("raw_response") or ""),
                "evaluation": _evaluate_case(case, list(details.get("books", []))),
                "error": None,
            })
        except Exception as exc:
            runs.append({
                "requested_model": requested_model,
                "resolved_model": requested_model,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
                "elapsed_ms": 0.0,
                "usage": {
                    "calls": 0,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "billable_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                    "records": [],
                },
                "cost": _estimate_cost(requested_model, {
                    "billable_input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                }),
                "books": [],
                "raw_response": "",
                "evaluation": {
                    "expected_count": len(case["expected_books"]),
                    "predicted_count": 0,
                    "identified_count": 0,
                    "matched_count": 0,
                    "author_count": 0,
                    "overall_score": 0.0,
                    "missed_labels": [
                        expected["label"] for expected in case["expected_books"]
                    ],
                    "mismatch_labels": [],
                    "per_book": [],
                    "unexpected_predictions": [],
                },
                "error": str(exc),
            })

    return {
        "case": {
            "id": case["id"],
            "name": case["name"],
            "description": case["description"],
            "image_path": str(case["image_path"]),
            "expected_books": case["expected_books"],
        },
        "runs": runs,
        "pricing_source": "OpenAI pricing page snapshot as of 2026-03-15",
    }
