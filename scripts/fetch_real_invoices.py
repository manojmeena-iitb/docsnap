"""Download the real invoices listed in data/real_sources.json and keep only the listed pages.

The files are not stored in git (see data/SOURCES.md). Every download is checked against
its SHA-256 checksum, so a broken link or a changed file stops with a clear message.
  uv run python scripts/fetch_real_invoices.py
"""

import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

SOURCES = Path("data/real_sources.json")
CACHE = Path("data/raw/web")
OUT = Path("data/eval/docs")
USER_AGENT = "Mozilla/5.0 (DocSnap eval data; +https://github.com/manojmeena-iitb/docsnap)"
TIMEOUT_SECONDS = 120


def sha256(data: bytes) -> str:
    """Fingerprint of a file's bytes; any change to the file changes it."""
    return hashlib.sha256(data).hexdigest()


def parse_pages(spec: str) -> list[int]:
    """Turn a page spec like '2' or '1-2' into zero-based page indexes."""
    first, _, last = spec.partition("-")
    return list(range(int(first) - 1, int(last or first)))


def download(url: str) -> bytes:
    """Fetch a URL and return its bytes."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def get_source(entry: dict) -> bytes:
    """Return the source PDF, from the local cache if unchanged, else freshly downloaded."""
    cached = CACHE / f"{entry['id']}_source.pdf"
    if cached.exists() and sha256(cached.read_bytes()) == entry["sha256"]:
        return cached.read_bytes()
    data = download(entry["url"])
    if sha256(data) != entry["sha256"]:
        raise ValueError("the file at this link has changed since it was checked (checksum differs)")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def extract_pages(pdf: bytes, pages: list[int], out_path: Path) -> None:
    """Save only the given pages of a PDF to out_path."""
    reader = PdfReader(io.BytesIO(pdf))
    if pages[-1] >= len(reader.pages):
        raise ValueError(f"needs page {pages[-1] + 1}, but the PDF has {len(reader.pages)} pages")
    writer = PdfWriter()
    for index in pages:
        writer.add_page(reader.pages[index])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as file:
        writer.write(file)


def main() -> None:
    entries = json.loads(SOURCES.read_text())
    failed = []
    for entry in entries:
        try:
            pdf = get_source(entry)
            extract_pages(pdf, parse_pages(entry["pages"]), OUT / f"{entry['id']}.pdf")
            print(f"ok      {entry['id']}")
        except (OSError, ValueError, PyPdfError) as error:
            failed.append(entry["id"])
            print(f"FAILED  {entry['id']}: {error}\n        {entry['url']}")
    print(f"\n{len(entries) - len(failed)} of {len(entries)} invoices ready in {OUT}/")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
