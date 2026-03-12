"""Download Open Library bulk data dumps.

Downloads the monthly exports of Open Library catalog data for local
indexing. Currently downloads works (~2.9GB) and authors (~0.5GB) dumps.
Editions (~9.2GB) can be added later for ISBN data.

Usage:
    uv run python scripts/download_openlibrary.py           # all dumps
    uv run python scripts/download_openlibrary.py authors    # just authors
    uv run python scripts/download_openlibrary.py works      # just works
"""

import sys
import time
from pathlib import Path
from urllib.request import urlretrieve

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "openlibrary"

DUMPS = {
    "authors": {
        "url": "https://openlibrary.org/data/ol_dump_authors_latest.txt.gz",
        "desc": "Author records (~0.5GB)",
    },
    "works": {
        "url": "https://openlibrary.org/data/ol_dump_works_latest.txt.gz",
        "desc": "Work records (~2.9GB)",
    },
    # Uncomment to include editions (adds ISBN, publisher, page count):
    # "editions": {
    #     "url": "https://openlibrary.org/data/ol_dump_editions_latest.txt.gz",
    #     "desc": "Edition records (~9.2GB)",
    # },
}


def download_file(url: str, dest: Path) -> None:
    """Download a file with progress reporting."""
    if dest.exists():
        size_gb = dest.stat().st_size / 1e9
        print(f"  Already exists: {dest.name} ({size_gb:.2f} GB)")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".tmp")

    print(f"  URL:  {url}")
    print(f"  Dest: {dest}")

    start = time.monotonic()
    last_report = start

    def progress(block_num: int, block_size: int, total_size: int) -> None:
        nonlocal last_report
        downloaded = block_num * block_size
        now = time.monotonic()
        if now - last_report < 2.0 and downloaded < total_size:
            return
        last_report = now
        elapsed = now - start
        speed = downloaded / elapsed if elapsed > 0 else 0
        if total_size > 0:
            pct = downloaded / total_size * 100
            remaining = (total_size - downloaded) / speed if speed > 0 else 0
            print(
                f"\r  {pct:5.1f}% | {downloaded / 1e9:.2f}/{total_size / 1e9:.2f} GB"
                f" | {speed / 1e6:.1f} MB/s | ETA {remaining / 60:.0f}m",
                end="",
                flush=True,
            )
        else:
            print(
                f"\r  {downloaded / 1e9:.2f} GB | {speed / 1e6:.1f} MB/s",
                end="",
                flush=True,
            )

    try:
        urlretrieve(url, str(temp), reporthook=progress)
    except Exception:
        print(f"\n  Download failed. Partial file left at: {temp}")
        raise

    print()
    temp.rename(dest)

    elapsed = time.monotonic() - start
    size = dest.stat().st_size
    print(f"  Done: {size / 1e9:.2f} GB in {elapsed / 60:.1f} min")


def main() -> None:
    which = sys.argv[1:] if len(sys.argv) > 1 else list(DUMPS.keys())

    for name in which:
        if name not in DUMPS:
            print(f"Unknown dump: {name}. Available: {', '.join(DUMPS)}")
            sys.exit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for name in which:
        info = DUMPS[name]
        print(f"\n[{name}] {info['desc']}")
        dest = DATA_DIR / f"ol_dump_{name}_latest.txt.gz"
        download_file(info["url"], dest)

    print(f"\nAll downloads complete. Files in: {DATA_DIR}")


if __name__ == "__main__":
    main()
