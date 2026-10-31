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


def test_indian_number():
    assert indian_number(999.0) == "999.00"
    assert indian_number(277552.0) == "2,77,552.00"
    assert indian_number(1595357.14) == "15,95,357.14"
    assert indian_number(-0.2) == "-0.20"


@pytest.mark.parametrize("path", [k for k in KEYS if load(k)["expected_status"] == "ok"], ids=lambda p: p.stem)
def test_correct_invoice_adds_up(path):
    key = load(path)
    items = sum(i["amount"] for i in key["line_items"])
    assert abs(items - key["subtotal"]) <= 1, "line items do not add up to the subtotal"
    extra = (key["service_charge"] or 0) - (key["discount"] or 0)
    assert abs(key["subtotal"] + extra + key["tax"] - key["total"]) <= 1, "subtotal + tax does not equal total"
    assert date.fromisoformat(key["invoice_date"]) <= date.today()
    assert key["vendor_gstin"] is None or GSTIN.match(key["vendor_gstin"])
