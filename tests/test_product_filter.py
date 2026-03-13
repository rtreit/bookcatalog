"""Tests for the product filter heuristic classifier."""

import pytest

from bookcatalog.research.product_filter import (
    PRODUCT_THRESHOLD,
    compute_product_score,
    is_likely_product,
)


class TestComputeProductScore:
    """Test product score computation for various input types."""

    # -- Definite books (should score low) --

    @pytest.mark.parametrize("title", [
        "Boy in a China Shop: Life, Clay and Everything",
        "Complete Pottery Techniques: Design, Form, Throw, Decorate and More",
        "Irish Fairy Tales and Folklore",
        "Mastering Hand Building: Techniques, Tips, and Tricks for Slabs, Coils, and More",
        "Studio Ghibli: The Complete Works",
        "The Hardware Hacking Handbook: Breaking Embedded Security with Hardware Attacks",
        "Van Richten's Guide to Ravenloft",
        "Backcountry Skiing: Skills for Ski Touring and Ski Mountaineering",
        "The Ninth Hour: A Novel",
        "Prayers & Promises for First Responders",
        "1984",
    ])
    def test_books_score_low(self, title: str) -> None:
        score = compute_product_score(title)
        assert score < PRODUCT_THRESHOLD, (
            f"Book title '{title}' scored {score:.2f}, expected < {PRODUCT_THRESHOLD}"
        )

    # -- Definite products (should score high) --
    # Use full Amazon-style product titles for realistic testing
    @pytest.mark.parametrize("title", [
        "10Pcs PAM8403 Module 2 x 3W Class D Mini Digital Power Amplifier Module 2.5-5V Input Audio Speaker Sound Board Amplificador Volume Control",
        "BOJACK 1000 Pcs 25 Values Resistor Kit 1 Ohm-1M Ohm with 1% 1/2W Metal Film Resistors Assortment",
        "Arduino Uno REV3 [A000066] - ATmega328P Microcontroller, 16MHz, 14 Digital I/O Pins, 6 Analog Inputs, 32KB Flash, USB Connectivity, Compatible with Arduino IDE for DIY Projects and Prototyping",
        "SanDisk 2TB Extreme Portable SSD - Up to 1050MB/s, USB-C, USB 3.2 Gen 2, IP65 Water and Dust Resistance, Updated Firmware - External Solid State Drive - SDSSDE61-2T00-G25",
        "USB Tester Type C Meter - USB Digital Multimeter Amperage Power Capacity Reader & USB C Current Voltmeter & Voltage Monitor Tester & Amp Amperage Charging USB Detector Checker DC 0-30V/0-6.5A",
        "PEIPU Nitrile Gloves,Disposable Cleaning Gloves,(Large, 100-Count) Powder Free, Latex Free,Rubber Free,Ultra-Strong,Food Handling Use, Single Use Non-Sterile Protective Gloves",
        "Raspberry Pi Zero 2 W (Wireless / Bluetooth) 2021 (RPi Zero 2W)",
        "Cherry MX Board 3.0 S Wired Gamer Mechanical Keyboard with Aluminum Housing - MX Brown Switches (Slight Clicky) for Gaming and Office - Customizable RGB Backlighting - Full Size - Black",
    ])
    def test_products_score_high(self, title: str) -> None:
        score = compute_product_score(title)
        assert score >= PRODUCT_THRESHOLD, (
            f"Product '{title}' scored {score:.2f}, expected >= {PRODUCT_THRESHOLD}"
        )

    # -- Fragments (should score high) --

    @pytest.mark.parametrize("title", [
        "Water-Resistant",
        "UL Listed",
        "Large (1168L)",
    ])
    def test_fragments_score_high(self, title: str) -> None:
        score = compute_product_score(title)
        assert score >= PRODUCT_THRESHOLD, (
            f"Fragment '{title}' scored {score:.2f}, expected >= {PRODUCT_THRESHOLD}"
        )

    def test_empty_string_scores_moderate(self) -> None:
        assert compute_product_score("") == 0.5

    def test_score_bounded_zero_to_one(self) -> None:
        for text in ["simple", "x" * 500, "USB 5V 10A 100W module adapter cable"]:
            score = compute_product_score(text)
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for '{text}'"


class TestIsLikelyProduct:
    """Test the boolean classification function."""

    def test_book_not_filtered(self) -> None:
        assert not is_likely_product("The Great Gatsby")

    def test_product_filtered(self) -> None:
        assert is_likely_product(
            "BOJACK 1000 Pcs 25 Values Resistor Kit 1 Ohm-1M Ohm "
            "with 1% 1/2W Metal Film Resistors Assortment"
        )

    def test_custom_threshold(self) -> None:
        text = "Some ambiguous text"
        score = compute_product_score(text)
        assert is_likely_product(text, threshold=0.0)
        assert not is_likely_product(text, threshold=1.0)

    def test_floating_point_edge_case(self) -> None:
        """Scores that round to the threshold should still be caught."""
        # This tests that round(score, 2) is used in comparison
        # to avoid floating-point precision issues like 0.3999... < 0.40
        text = (
            "MAGCOMSEN Women's Long Sleeve Rash Guard Shirts for Hiking, "
            "Running and Fishing - UV Protection - Light Grey"
        )
        assert is_likely_product(text, threshold=0.40)
