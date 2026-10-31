"""Checks on the answer keys themselves, so a typo in a key is caught before it skews the scores."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from review_ground_truth import indian_number

KEYS = sorted(Path("data/eval/ground_truth").glob("*.json"))
GSTIN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def problems(key: dict) -> list[str]:
    """The checks from SPEC.md, run on an answer key. Empty list = the bill is consistent."""
    found = []
    items = sum(i["amount"] for i in key["line_items"])
    subtotal, total = key["subtotal"], key["total"]
    if abs(items - subtotal) > 1 and abs(items - total) > 1:
        found.append("line items do not add up")
    before_tax = subtotal - (key["discount"] or 0) + (key["service_charge"] or 0)
    if abs(before_tax + (key["tax"] or 0) - total) > 1 and abs(before_tax - total) > 1:
        found.append("total does not match")
    try:
        if date.fromisoformat(key["invoice_date"]) > date.today():
            found.append("date is in the future")
    except ValueError:
        found.append("not a real date")
    if key["vendor_gstin"] and not GSTIN.match(key["vendor_gstin"]):
        found.append("GSTIN format is wrong")
    return found


def test_indian_number():
    assert indian_number(999.0) == "999.00"
    assert indian_number(277552.0) == "2,77,552.00"
    assert indian_number(1595357.14) == "15,95,357.14"
    assert indian_number(-0.2) == "-0.20"


@pytest.mark.parametrize("path", KEYS, ids=lambda p: p.stem)
def test_key_passes_checks_only_if_marked_ok(path):
    key = load(path)
    if key["expected_status"] == "ok":
        assert problems(key) == []
    else:
        assert problems(key), "a bill marked needs_review must break at least one check"
