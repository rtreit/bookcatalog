"""Input preprocessing utilities for splitting and cleaning raw title input."""


def split_order_items(text: str, delimiter: str = "|") -> list[str]:
    """Split a single order string into individual item titles.

    Handles Amazon-style order strings where multiple products are separated
    by a delimiter (typically a pipe character).

    Args:
        text: Raw order string, potentially containing multiple items.
        delimiter: Character to split on. Defaults to "|".

    Returns:
        List of cleaned, non-empty item strings.
    """
    parts = text.split(delimiter)
    return [p.strip() for p in parts if p.strip()]


def preprocess_input(
    lines: list[str],
    delimiter: str | None = None,
) -> list[str]:
    """Preprocess a list of input lines into individual title candidates.

    When a delimiter is provided, each line is split on that delimiter first,
    expanding multi-item order strings into separate entries.

    Args:
        lines: Raw input lines (one per entry or Amazon order format).
        delimiter: If set, split each line on this character. Common values
            are "|" for Amazon orders. None means no splitting.

    Returns:
        Flat list of cleaned, non-empty title strings.
    """
    results: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if delimiter:
            results.extend(split_order_items(line, delimiter))
        else:
            results.append(line)
    return results
