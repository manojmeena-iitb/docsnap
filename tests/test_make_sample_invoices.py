"""Tests for the sample-bill generator."""

import json
from pathlib import Path

import make_sample_invoices as gen


def test_gstin_check_char_matches_real_gstins():
    for gstin in ["36AAKPE9014C1Z2", "33AAACB2894G1ZU", "27AAJCM7667D1Z4", "09AAGFA5022L1ZH"]:
        assert gen.gstin_check_char(gstin[:14]) == gstin[14]


def test_rupees_in_words():
    assert gen.rupees_in_words(gen.money("277552")) == "Rupees Two Lakh Seventy Seven Thousand Five Hundred Fifty Two Only"
    assert gen.rupees_in_words(gen.money("84765.21")) == (
        "Rupees Eighty Four Thousand Seven Hundred Sixty Five and Twenty One Paise Only")


def test_committed_keys_match_the_generator():
    """The keys in the repo are exactly what the generator makes (no hand edits, same every run)."""
    for doc_id, key in gen.build_keys().items():
        assert json.loads(Path(f"data/eval/ground_truth/{doc_id}.json").read_text()) == key, doc_id


def test_set_has_every_kind_and_five_mistakes():
    bills = gen.BILLS
    assert {b.kind for b in bills} == {"gst_intra", "gst_inter", "retail", "restaurant", "bill_of_supply"}
    assert len({b.mistake for b in bills if b.mistake}) == 5
