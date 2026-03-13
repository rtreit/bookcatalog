"""Fast pre-filter to identify non-book products before expensive FTS search.

Uses lightweight heuristics (regex patterns, keyword detection, structural
analysis) to score how likely an input string is a commercial product rather
than a book title. Items above the threshold are skipped entirely, avoiding
costly FTS5 queries against the database.

Designed for Amazon order export data where the majority of items are
electronics, household goods, and other non-book products.
"""

import re


# -- Technical specification patterns --
# Voltage, current, power, frequency, storage, resistance
_TECH_SPEC_PATTERN = re.compile(
    r"""
    (?:^|[\s,(/])                     # preceded by whitespace/separator
    (?:
        \d+\.?\d*\s*(?:k|m|M|G|T)?(?:Hz|hz)       |  # frequency
        \d+\.?\d*\s*(?:m|u|M)?(?:A|Ah|mAh)         |  # current/capacity
        \d+\.?\d*\s*(?:m|k)?(?:V|v)(?![a-zA-Z])    |  # voltage
        \d+\.?\d*\s*(?:m|k)?W\b                     |  # wattage
        \d+\.?\d*\s*(?:k|M)?(?:Ohm|ohm)\b          |  # resistance
        \d+\.?\d*\s*(?:G|T|M)B\b                    |  # storage
        \d+\.?\d*\s*(?:mm|cm|in|ft|inch|feet)\b     |  # dimensions
        \d+\.?\d*\s*(?:oz|lbs?|kg|g)\b              |  # weight
        \d+\s*(?:pin|Pin)\b                         |  # pin count
        \d+\s*(?:bit|Bit)\b                         |  # bit depth
        \d+x\d+                                     |  # dimensions NxN
        (?:USB|HDMI|SPI|I2C|UART|SMA|IIC)\b         |  # interface protocols
        (?:WiFi|Wi-Fi|Bluetooth|BLE|NFC|LoRa)\b     |  # wireless protocols
        (?:RGB|LED|LCD|PCB|GPIO|ADC|DAC)\b           |  # component acronyms
        \d+\s*(?:DPI|dpi|RPM|rpm|Mbps|Gbps)\b          # performance specs
    )
    """,
    re.VERBOSE,
)

# Model number patterns: alphanumeric codes with digits mixed in
_MODEL_NUMBER_PATTERN = re.compile(
    r"\b[A-Z]{1,5}[\-]?\d{2,}[A-Z0-9\-]*\b"  # e.g., PAM8403, HS103P4, SH-U09C5
    r"|\b\d{2,}[A-Z][A-Z0-9\-]+\b"            # e.g., 2N2222, 24MHz
)

# Quantity phrases
_QUANTITY_PATTERN = re.compile(
    r"""
    \b\d+\s*(?:Pcs|pcs|PCS|Pack|pack|Count|count|Sets?|sets?|Rolls?|rolls?|Pairs?|pairs?)\b |
    \bPack\s+of\s+\d+\b |
    \b\d+[\-]?(?:Count|Pack)\b |
    \b\d+\s*x\s+\d+\b
    """,
    re.VERBOSE,
)

# Product category keywords (strong non-book signals)
_PRODUCT_KEYWORDS = frozenset({
    "adapter", "amplifier", "antenna", "backpack", "bandage", "battery",
    "board", "breadboard", "buzzer", "cable", "caliper", "capacitor",
    "carabiner", "charger", "circuit", "clip", "connector", "converter",
    "diode", "dongle", "dressing", "earbuds", "flashlight", "gauze",
    "glove", "gloves", "headlamp", "headset", "hub", "inductor",
    "jumper", "keyboard", "led", "lubricant", "mat", "membrane",
    "microcontroller", "microsd", "module", "monitor", "mouse",
    "multimeter", "oscilloscope", "pad", "paintballs", "pants", "plug",
    "potentiometer", "programmer", "protector", "receiver", "resistor",
    "scissors", "screwdriver", "sensor", "shears", "shield", "shirt",
    "shirts", "soldering", "speaker", "splint", "ssd", "stabilizer",
    "strip", "surge", "switch", "tape", "tester", "toggle",
    "transistor", "tweezers", "vest", "voltmeter", "wire", "wrench",
})

# Two-word product phrases
_PRODUCT_PHRASES = [
    "power supply", "power bank", "power strip", "mouse pad",
    "circuit board", "memory card", "sd card", "micro sd",
    "load cell", "test lead", "safety vest", "safety glasses",
    "work gloves", "cargo pants", "rash guard", "ski mask",
    "face mask", "dog training", "wall charger", "smart plug",
    "gaming mouse", "mechanical keyboard", "led matrix",
    "raspberry pi", "development board", "usb cable",
    "micro hdmi", "usb hub", "portable charger",
    "cloth tape", "gauze roll", "elastic bandage",
    "nitrile gloves", "push button",
    "wound dressing", "first aid", "long sleeve",
    "emergency response", "ski patrol",
]

# Compatibility phrases
_COMPAT_PATTERN = re.compile(
    r"(?:Compatible with|Works with|for (?:Arduino|Raspberry|iPhone|Samsung|MacBook|iPad))",
    re.IGNORECASE,
)

# Book-like signals (counter-indicators)
_BOOK_KEYWORDS = frozenset({
    "novel", "memoir", "autobiography", "biography", "anthology",
    "tales", "stories", "poems", "poetry", "essays", "folklore",
    "guide", "handbook", "manual", "techniques", "mastering",
    "introduction", "principles", "foundations", "history",
    "prayers", "promises", "adventures",
})

# Common publishing-style subtitle pattern: "Main Title: Descriptive Subtitle"
_SUBTITLE_PATTERN = re.compile(r"^[A-Z][^:]{3,40}:\s+[A-Z]")


def compute_product_score(text: str) -> float:
    """Score how likely a string is a commercial product vs. a book title.

    Returns a value between 0.0 (definitely a book) and 1.0 (definitely a
    product). Items scoring above a threshold (e.g., 0.65) can be skipped
    to avoid expensive FTS searches.

    The scoring uses multiple lightweight heuristics that are individually
    weak but compound effectively:
    - Technical specifications (voltages, frequencies, etc.)
    - Model numbers
    - Quantity phrases
    - Product category keywords
    - Structural patterns (length, comma density, ALL-CAPS words)
    - Compatibility phrases

    Book-like counter-signals reduce the score to avoid false filtering
    of books about technical topics (e.g., "The Hardware Hacking Handbook").

    Args:
        text: Raw input string (e.g., an Amazon order line item).

    Returns:
        Product likelihood score between 0.0 and 1.0.
    """
    if not text or not text.strip():
        return 0.5

    text = text.strip()
    text_lower = text.lower()
    score = 0.0

    # Technical specifications: count matches
    tech_matches = _TECH_SPEC_PATTERN.findall(text)
    tech_count = len(tech_matches)
    if tech_count >= 3:
        score += 0.35
    elif tech_count >= 1:
        score += 0.15

    # Model numbers
    model_matches = _MODEL_NUMBER_PATTERN.findall(text)
    if len(model_matches) >= 2:
        score += 0.20
    elif len(model_matches) >= 1:
        score += 0.10

    # Quantity phrases
    if _QUANTITY_PATTERN.search(text):
        score += 0.15

    # Product category keywords
    words_lower = set(text_lower.split())
    product_word_count = sum(1 for w in words_lower if w in _PRODUCT_KEYWORDS)
    for phrase in _PRODUCT_PHRASES:
        if phrase in text_lower:
            product_word_count += 1
    if product_word_count >= 3:
        score += 0.30
    elif product_word_count >= 2:
        score += 0.20
    elif product_word_count >= 1:
        score += 0.10

    # Compatibility phrases
    if _COMPAT_PATTERN.search(text):
        score += 0.15

    # Structural signals
    # Very long descriptions are more likely products
    if len(text) > 150:
        score += 0.10
    elif len(text) > 100:
        score += 0.05

    # Comma density (product listings often have many commas)
    comma_count = text.count(",")
    if comma_count >= 5:
        score += 0.10
    elif comma_count >= 3:
        score += 0.05

    # ALL-CAPS words (brand names): count words that are 3+ chars and all caps
    allcaps_words = [w for w in text.split() if len(w) >= 3 and w.isupper() and w.isalpha()]
    if len(allcaps_words) >= 2:
        score += 0.10
    elif len(allcaps_words) >= 1:
        score += 0.05

    # Very short text (fragments like "Water-Resistant", "UL Listed")
    # These are likely fragments from pipe-splitting, not standalone titles.
    # Exception: single words that look like years (e.g., "1984") since
    # many classic books have numeric titles.
    word_count = len(text.split())
    looks_like_year = (
        word_count == 1
        and text.isdigit()
        and 1800 <= int(text) <= 2100
    )
    if word_count <= 2 and not looks_like_year and not any(
        w in text_lower.split() for w in _BOOK_KEYWORDS
    ):
        # Single or two-word fragments are almost never book titles
        # unless they contain a book keyword like "novel" or "tales"
        score += 0.50
    elif word_count <= 4 and not any(w in text_lower.split() for w in _BOOK_KEYWORDS):
        # Short non-book phrases (e.g., "Large (1168L)", "UL Listed")
        if any(c.isdigit() for c in text):
            score += 0.15

    # -- Counter-signals (book-like patterns, reduce score) --
    book_word_count = sum(1 for w in words_lower if w in _BOOK_KEYWORDS)
    if book_word_count >= 2:
        score -= 0.30
    elif book_word_count >= 1:
        score -= 0.15

    # Subtitle pattern ("Title: Subtitle" with capitalized words)
    if _SUBTITLE_PATTERN.match(text):
        score -= 0.10

    # Short, clean titles (fewer than 60 chars, few special chars)
    if len(text) < 60:
        special_chars = sum(1 for c in text if not c.isalnum() and c not in " :'-&,.()")
        if special_chars <= 2:
            score -= 0.10

    return max(0.0, min(score, 1.0))


# Default threshold: items at or above this are classified as products and skipped
PRODUCT_THRESHOLD = 0.40


def is_likely_product(text: str, threshold: float = PRODUCT_THRESHOLD) -> bool:
    """Quick check: is this text likely a commercial product, not a book?

    Args:
        text: Raw input string.
        threshold: Score above which the item is classified as a product.
            Default 0.40 is tuned for Amazon order data.

    Returns:
        True if the item is likely a product and should be skipped.
    """
    return round(compute_product_score(text), 2) >= threshold
