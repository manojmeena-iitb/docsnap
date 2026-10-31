"""Tests for the real-invoice download script. No test touches the internet."""

import io

import pytest
from pypdf import PdfReader, PdfWriter

import fetch_real_invoices as fetch


def make_pdf(page_count: int) -> bytes:
    """A blank PDF with the given number of pages."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_parse_pages():
    assert fetch.parse_pages("2") == [1]
    assert fetch.parse_pages("1-2") == [0, 1]


def test_changed_file_is_rejected_and_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "CACHE", tmp_path)
    monkeypatch.setattr(fetch, "download", lambda url: b"different file")
    entry = {"id": "real_x", "url": "https://example.org/x.pdf", "sha256": fetch.sha256(b"original file")}
    with pytest.raises(ValueError, match="changed"):
        fetch.get_source(entry)
    assert not (tmp_path / "real_x_source.pdf").exists()


def test_unchanged_cache_is_used_without_downloading(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "CACHE", tmp_path)
    (tmp_path / "real_x_source.pdf").write_bytes(b"original file")

    def no_download(url):
        raise AssertionError("should not download")

    monkeypatch.setattr(fetch, "download", no_download)
    entry = {"id": "real_x", "url": "https://example.org/x.pdf", "sha256": fetch.sha256(b"original file")}
    assert fetch.get_source(entry) == b"original file"


def test_extract_keeps_only_listed_pages(tmp_path):
    out = tmp_path / "doc.pdf"
    fetch.extract_pages(make_pdf(5), [1, 2], out)
    assert len(PdfReader(out).pages) == 2


def test_extract_rejects_missing_page(tmp_path):
    with pytest.raises(ValueError, match="needs page 3"):
        fetch.extract_pages(make_pdf(2), [2], tmp_path / "doc.pdf")
