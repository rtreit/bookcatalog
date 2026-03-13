"""Benchmark script for book matcher performance and accuracy analysis.

Measures per-item timing breakdown (FTS queries, scoring, total) and
accuracy (correct matches, false positives, false negatives) across
different matching strategies.

Usage:
    uv run python scripts/benchmark_matcher.py
"""

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bookcatalog.research.local_search import LocalBookSearch
from bookcatalog.research.product_filter import compute_product_score, is_likely_product

# Representative subset: 8 books + 12 non-book products + edge cases
BENCHMARK_ITEMS: list[dict[str, str | bool]] = [
    # --- Actual books (should match) ---
    {"input": "Boy in a China Shop: Life, Clay and Everything (-)", "is_book": True, "expected_title": "Boy in a China Shop"},
    {"input": "Complete Pottery Techniques: Design, Form, Throw, Decorate and More, with Workshops from Professional Makers", "is_book": True, "expected_title": "Complete Pottery Techniques"},
    {"input": "Irish Fairy Tales and Folklore", "is_book": True, "expected_title": "Irish Fairy Tales and Folklore"},
    {"input": "Mastering Hand Building: Techniques, Tips, and Tricks for Slabs, Coils, and More (Mastering Ceramics)", "is_book": True, "expected_title": "Mastering hand building"},
    {"input": "Studio Ghibli: The Complete Works", "is_book": True, "expected_title": "Studio Ghibli"},
    {"input": "The Hardware Hacking Handbook: Breaking Embedded Security with Hardware Attacks", "is_book": True, "expected_title": "The Hardware Hacking Handbook"},
    {"input": "Van Richten's Guide to Ravenloft", "is_book": True, "expected_title": "Van Richten's Guide to Ravenloft"},
    {"input": "Backcountry Skiing: Skills for Ski Touring and Ski Mountaineering (Mountaineers Outdoor Expert)", "is_book": True, "expected_title": "Backcountry Skiing"},
    # --- Non-book products (should NOT match) ---
    {"input": "10Pcs PAM8403 Module 2 x 3W Class D Mini Digital Power Amplifier Module 2.5-5V Input Audio Speaker Sound Board Amplificador Volume Control", "is_book": False},
    {"input": "BOJACK 1000 Pcs 25 Values Resistor Kit 1 Ohm-1M Ohm with 1% 1/2W Metal Film Resistors Assortment", "is_book": False},
    {"input": "Cherry MX Board 3.0 S Wired Gamer Mechanical Keyboard with Aluminum Housing - MX Brown Switches (Slight Clicky) for Gaming and Office - Customizable RGB Backlighting - Full Size - Black", "is_book": False},
    {"input": "Raspberry Pi Zero 2 W (Wireless / Bluetooth) 2021 (RPi Zero 2W)", "is_book": False},
    {"input": "SanDisk 2TB Extreme Portable SSD - Up to 1050MB/s, USB-C, USB 3.2 Gen 2, IP65 Water and Dust Resistance, Updated Firmware - External Solid State Drive - SDSSDE61-2T00-G25", "is_book": False},
    {"input": "MAGCOMSEN Women's Long Sleeve Rash Guard Shirts for Hiking, Running and Fishing - UV Protection - Light Grey", "is_book": False},
    {"input": "Nexcare Durable Cloth Tape, Woven Tape, Securely Holds Bulky Wound Dressing - 1 In x 10 Yds, 2 Rolls of Tape", "is_book": False},
    {"input": "Arduino Uno REV3 [A000066] - ATmega328P Microcontroller, 16MHz, 14 Digital I/O Pins, 6 Analog Inputs, 32KB Flash, USB Connectivity, Compatible with Arduino IDE for DIY Projects and Prototyping", "is_book": False},
    {"input": "PEIPU Nitrile Gloves,Disposable Cleaning Gloves,(Large, 100-Count) Powder Free, Latex Free,Rubber Free,Ultra-Strong,Food Handling Use, Single Use Non-Sterile Protective Gloves", "is_book": False},
    {"input": "USB Tester Type C Meter - USB Digital Multimeter Amperage Power Capacity Reader & USB C Current Voltmeter & Voltage Monitor Tester & Amp Amperage Charging USB Detector Checker DC 0-30V/0-6.5A", "is_book": False},
    {"input": "Water-Resistant", "is_book": False},
    {"input": "Search and Rescue, Ski Patrol, Emergency Response - Black", "is_book": False},
]


@dataclass
class ItemTiming:
    """Timing breakdown for a single item."""
    input_title: str
    is_book: bool
    total_ms: float = 0.0
    search_ms: float = 0.0
    scoring_ms: float = 0.0
    num_fts_queries: int = 0
    num_candidates: int = 0
    matched: bool = False
    decision: str | None = None
    confidence: float | None = None
    matched_title: str | None = None


@dataclass
class BenchmarkResult:
    """Aggregate benchmark results."""
    strategy_name: str
    total_items: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    book_items: int = 0
    nonbook_items: int = 0
    true_positives: int = 0  # books correctly matched
    false_positives: int = 0  # non-books incorrectly matched
    true_negatives: int = 0  # non-books correctly unmatched
    false_negatives: int = 0  # books incorrectly unmatched
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    items: list[ItemTiming] = field(default_factory=list)


def run_instrumented_match(
    search: LocalBookSearch,
    input_title: str,
) -> ItemTiming:
    """Run match_title with detailed timing instrumentation."""
    timing = ItemTiming(input_title=input_title, is_book=False)

    # Phase 1: Build search variants (same logic as match_title)
    search_queries = [input_title]
    input_lower = input_title.lower()
    by_idx = input_lower.rfind(" by ")
    title_part = input_title
    if by_idx > 0:
        title_part = input_title[:by_idx].strip()
        if title_part:
            search_queries.append(title_part)
    for sep in [":", " - "]:
        if sep in title_part:
            parts = title_part.split(sep, 1)
            main_title = parts[0].strip()
            subtitle = parts[1].strip()
            if main_title and len(main_title) > 2:
                search_queries.append(main_title)
            if subtitle and len(subtitle) > 3:
                search_queries.append(subtitle)

    # Phase 2: FTS search (timed)
    t_search_start = time.perf_counter()
    seen_keys: set[str] = set()
    all_candidates: list[dict] = []
    total_fts_queries = 0
    for query in search_queries:
        results = search.search(query, limit=10)
        total_fts_queries += 1
        for r in results:
            key = r.get("key", "")
            if key not in seen_keys:
                seen_keys.add(key)
                all_candidates.append(r)
    t_search_end = time.perf_counter()

    timing.search_ms = (t_search_end - t_search_start) * 1000
    timing.num_fts_queries = total_fts_queries
    timing.num_candidates = len(all_candidates)

    # Phase 3: Scoring (timed)
    t_score_start = time.perf_counter()
    best_score = 0.0
    best_result = None
    for result in all_candidates:
        score = search._score_result(input_title, result)
        if score > best_score:
            best_score = score
            best_result = result
    t_score_end = time.perf_counter()

    timing.scoring_ms = (t_score_end - t_score_start) * 1000

    # Classify using same thresholds as LocalBookSearch
    if best_result and best_score >= 0.85:
        timing.matched = True
        timing.decision = "book"
        timing.confidence = round(best_score, 4)
        timing.matched_title = best_result.get("title", "")
    elif best_result and best_score >= 0.60:
        authors = (best_result.get("authors") or "").strip()
        if authors:
            timing.matched = True
            timing.decision = "likely_book"
            timing.confidence = round(best_score, 4)
            timing.matched_title = best_result.get("title", "")

    return timing


def evaluate_benchmark(
    strategy_name: str,
    items: list[dict],
    timings: list[ItemTiming],
) -> BenchmarkResult:
    """Compute accuracy metrics from timings against ground truth."""
    result = BenchmarkResult(strategy_name=strategy_name)
    result.total_items = len(items)
    result.items = timings

    for item, timing in zip(items, timings):
        is_book = bool(item["is_book"])
        timing.is_book = is_book
        result.total_time_ms += timing.total_ms

        if is_book:
            result.book_items += 1
            if timing.matched:
                result.true_positives += 1
            else:
                result.false_negatives += 1
        else:
            result.nonbook_items += 1
            if timing.matched:
                result.false_positives += 1
            else:
                result.true_negatives += 1

    result.avg_time_ms = result.total_time_ms / max(result.total_items, 1)

    tp = result.true_positives
    fp = result.false_positives
    fn = result.false_negatives
    result.precision = tp / max(tp + fp, 1)
    result.recall = tp / max(tp + fn, 1)
    if result.precision + result.recall > 0:
        result.f1 = 2 * (result.precision * result.recall) / (result.precision + result.recall)

    return result


def print_result(result: BenchmarkResult) -> None:
    """Print a formatted benchmark result."""
    print(f"\n{'=' * 70}")
    print(f"Strategy: {result.strategy_name}")
    print(f"{'=' * 70}")
    print(f"  Total items:      {result.total_items}")
    print(f"  Total time:       {result.total_time_ms:.1f} ms")
    print(f"  Avg time/item:    {result.avg_time_ms:.1f} ms")
    print(f"  Projected (106):  {result.avg_time_ms * 106 / 1000:.1f} s")
    print()
    print(f"  Accuracy:")
    print(f"    True positives:  {result.true_positives}/{result.book_items} books matched correctly")
    print(f"    False positives: {result.false_positives}/{result.nonbook_items} non-books matched (BAD)")
    print(f"    True negatives:  {result.true_negatives}/{result.nonbook_items} non-books rejected correctly")
    print(f"    False negatives: {result.false_negatives}/{result.book_items} books missed (BAD)")
    print(f"    Precision:       {result.precision:.1%}")
    print(f"    Recall:          {result.recall:.1%}")
    print(f"    F1 Score:        {result.f1:.1%}")
    print()

    # Per-item details
    print(f"  {'Item':<60} {'Time':>8} {'Result':>12} {'Conf':>6}")
    print(f"  {'-'*60} {'-'*8} {'-'*12} {'-'*6}")
    for timing in result.items:
        label = timing.input_title[:57] + "..." if len(timing.input_title) > 60 else timing.input_title
        time_str = f"{timing.total_ms:.0f}ms"
        if timing.matched:
            is_correct = timing.is_book
            marker = "OK" if is_correct else "FALSE+"
            result_str = f"{timing.decision} {marker}"
            conf_str = f"{timing.confidence:.0%}" if timing.confidence else ""
        else:
            is_correct = not timing.is_book
            marker = "OK" if is_correct else "MISS"
            result_str = f"no match {marker}"
            conf_str = ""
        print(f"  {label:<60} {time_str:>8} {result_str:>12} {conf_str:>6}")


def run_baseline_benchmark() -> BenchmarkResult:
    """Run the current (unmodified) matching strategy."""
    search = LocalBookSearch()
    timings: list[ItemTiming] = []

    for item in BENCHMARK_ITEMS:
        input_title = str(item["input"])
        t0 = time.perf_counter()
        timing = run_instrumented_match(search, input_title)
        timing.total_ms = (time.perf_counter() - t0) * 1000
        timings.append(timing)

    search.close()
    return evaluate_benchmark("Baseline (current code)", BENCHMARK_ITEMS, timings)


def run_prefilter_benchmark(threshold: float = 0.40) -> BenchmarkResult:
    """Run matching with product pre-filter to skip non-book items."""
    search = LocalBookSearch()
    timings: list[ItemTiming] = []

    for item in BENCHMARK_ITEMS:
        input_title = str(item["input"])
        t0 = time.perf_counter()

        # Pre-filter: skip items that look like products
        if is_likely_product(input_title, threshold=threshold):
            timing = ItemTiming(
                input_title=input_title,
                is_book=False,
                total_ms=0.0,
                matched=False,
                decision=None,
            )
            timing.total_ms = (time.perf_counter() - t0) * 1000
            timings.append(timing)
            continue

        timing = run_instrumented_match(search, input_title)
        timing.total_ms = (time.perf_counter() - t0) * 1000
        timings.append(timing)

    search.close()
    return evaluate_benchmark(
        f"Pre-filter (threshold={threshold})", BENCHMARK_ITEMS, timings
    )


def run_prefilter_plus_threshold_benchmark(
    product_threshold: float = 0.40,
    high_confidence: float = 0.85,
    moderate_confidence: float = 0.70,
) -> BenchmarkResult:
    """Run matching with pre-filter AND raised confidence thresholds."""
    search = LocalBookSearch()
    timings: list[ItemTiming] = []

    for item in BENCHMARK_ITEMS:
        input_title = str(item["input"])
        t0 = time.perf_counter()

        if is_likely_product(input_title, threshold=product_threshold):
            timing = ItemTiming(
                input_title=input_title, is_book=False, matched=False,
            )
            timing.total_ms = (time.perf_counter() - t0) * 1000
            timings.append(timing)
            continue

        timing = run_instrumented_match(search, input_title)

        # Override decision with raised thresholds
        if timing.confidence is not None:
            if timing.confidence >= high_confidence:
                timing.decision = "book"
                timing.matched = True
            elif timing.confidence >= moderate_confidence:
                timing.decision = "likely_book"
                timing.matched = True
            else:
                timing.decision = None
                timing.matched = False
                timing.confidence = None
                timing.matched_title = None

        timing.total_ms = (time.perf_counter() - t0) * 1000
        timings.append(timing)

    search.close()
    return evaluate_benchmark(
        f"Pre-filter + raised thresholds (prod={product_threshold}, "
        f"high={high_confidence}, mod={moderate_confidence})",
        BENCHMARK_ITEMS, timings,
    )


def run_integrated_benchmark() -> BenchmarkResult:
    """Run the fully integrated optimized matching (pre-filter + FTS token cap + raised thresholds).

    This tests the actual match_titles method as modified in local_search.py.
    """
    search = LocalBookSearch()
    titles = [str(item["input"]) for item in BENCHMARK_ITEMS]

    t0 = time.perf_counter()
    matches = search.match_titles(titles)
    total_ms = (time.perf_counter() - t0) * 1000

    timings: list[ItemTiming] = []
    per_item_ms = total_ms / max(len(titles), 1)
    for title, match in zip(titles, matches):
        timing = ItemTiming(
            input_title=title,
            is_book=False,
            total_ms=per_item_ms,
        )
        if match:
            timing.matched = True
            timing.decision = match.decision
            timing.confidence = match.confidence
            timing.matched_title = match.matched_title
        timings.append(timing)

    search.close()
    result = evaluate_benchmark("Integrated optimized (production)", BENCHMARK_ITEMS, timings)
    result.total_time_ms = total_ms
    result.avg_time_ms = per_item_ms
    return result


def print_filter_scores() -> None:
    """Print product filter scores for all benchmark items."""
    print("\nProduct Filter Scores:")
    print(f"  {'Item':<60} {'Score':>6} {'Filter':>8} {'Truth':>8}")
    print(f"  {'-'*60} {'-'*6} {'-'*8} {'-'*8}")
    for item in BENCHMARK_ITEMS:
        text = str(item["input"])
        score = compute_product_score(text)
        is_product = is_likely_product(text)
        is_book = bool(item["is_book"])
        label = text[:57] + "..." if len(text) > 60 else text
        filter_str = "SKIP" if is_product else "search"
        truth_str = "book" if is_book else "product"
        correct = (is_book and not is_product) or (not is_book and is_product)
        marker = "OK" if correct else "WRONG"
        print(f"  {label:<60} {score:>5.2f} {filter_str:>8} {truth_str:>8} {marker}")


def main() -> None:
    print("Book Matcher Performance Benchmark")
    print("===================================")
    print(f"Items: {len(BENCHMARK_ITEMS)} ({sum(1 for i in BENCHMARK_ITEMS if i['is_book'])} books, "
          f"{sum(1 for i in BENCHMARK_ITEMS if not i['is_book'])} non-books)")

    # Strategy 1: Baseline
    baseline = run_baseline_benchmark()
    print_result(baseline)

    # Timing breakdown
    print("\nTiming Breakdown (search vs scoring):")
    print(f"  {'Item':<50} {'Search':>10} {'Score':>10} {'FTS#':>5} {'Cands':>6}")
    print(f"  {'-'*50} {'-'*10} {'-'*10} {'-'*5} {'-'*6}")
    for timing in baseline.items:
        label = timing.input_title[:47] + "..." if len(timing.input_title) > 50 else timing.input_title
        print(f"  {label:<50} {timing.search_ms:>8.1f}ms {timing.scoring_ms:>8.1f}ms {timing.num_fts_queries:>5} {timing.num_candidates:>6}")

    total_search = sum(t.search_ms for t in baseline.items)
    total_scoring = sum(t.scoring_ms for t in baseline.items)
    total_total = sum(t.total_ms for t in baseline.items)
    print(f"\n  Total search time:  {total_search:.1f} ms ({total_search/total_total*100:.1f}%)")
    print(f"  Total scoring time: {total_scoring:.1f} ms ({total_scoring/total_total*100:.1f}%)")
    print(f"  Total overhead:     {total_total - total_search - total_scoring:.1f} ms")

    # Product filter scores
    print_filter_scores()

    # Strategy 2: Pre-filter only
    prefilter = run_prefilter_benchmark()
    print_result(prefilter)

    # Strategy 3: Pre-filter + raised thresholds (manual)
    optimized = run_prefilter_plus_threshold_benchmark()
    print_result(optimized)

    # Strategy 4: Integrated optimized (all changes in local_search.py)
    integrated = run_integrated_benchmark()
    print_result(integrated)

    # Summary comparison
    all_results = [baseline, prefilter, optimized, integrated]
    print(f"\n{'=' * 70}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 70}")
    print(f"  {'Strategy':<45} {'Time':>8} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Proj':>8}")
    print(f"  {'-'*45} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")
    for r in all_results:
        name = r.strategy_name[:42] + "..." if len(r.strategy_name) > 45 else r.strategy_name
        proj = f"{r.avg_time_ms * 106 / 1000:.1f}s"
        print(f"  {name:<45} {r.total_time_ms:>6.0f}ms {r.precision:>5.0%} {r.recall:>5.0%} {r.f1:>5.0%} {proj:>8}")

    # Save results for comparison
    output_path = Path(__file__).resolve().parent.parent / "data" / "benchmark_results.json"
    results_data = {}
    for r in all_results:
        key = r.strategy_name.split("(")[0].strip().lower().replace(" ", "_")
        results_data[key] = {
            "total_ms": r.total_time_ms,
            "avg_ms": r.avg_time_ms,
            "precision": r.precision,
            "recall": r.recall,
            "f1": r.f1,
            "true_positives": r.true_positives,
            "false_positives": r.false_positives,
            "true_negatives": r.true_negatives,
            "false_negatives": r.false_negatives,
        }
    output_path.write_text(json.dumps(results_data, indent=2))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
