"""Tests for the dark CHECK_QUOTES flag."""

from pathlib import Path

from vouch.check import check

DRAFT = (Path(__file__).parents[1] / "samples" / "draft.txt").read_text(encoding="utf-8")
FACTS = (Path(__file__).parents[1] / "samples" / "facts.txt").read_text(encoding="utf-8")
QUOTE = "This round lets us bring fast, fair payments to every small business in the region,"


def test_flag_is_off_by_default():
    assert not any(c.source == "quote" for c in check(DRAFT, FACTS).claims)


def test_quote_not_on_the_sheet_is_unsupported(monkeypatch):
    monkeypatch.setenv("CHECK_QUOTES", "on")
    q = [c for c in check(DRAFT, FACTS).claims if c.source == "quote"]
    assert len(q) == 1
    assert (q[0].state, q[0].reason) == ("unsupported", "Quote not on the approved sheet")
    assert DRAFT[q[0].start : q[0].end] == QUOTE


def test_quote_on_the_sheet_is_supported(monkeypatch):
    monkeypatch.setenv("CHECK_QUOTES", "on")
    sheet = FACTS + f"Quote: {QUOTE}\n"
    q = [c for c in check(DRAFT, sheet).claims if c.source == "quote"]
    assert (q[0].state, q[0].fact_id) == ("supported", "F9")


def test_short_quoted_phrases_are_not_speech(monkeypatch):
    monkeypatch.setenv("CHECK_QUOTES", "on")
    assert not any(c.source == "quote" for c in check('It is a "Series A" round.', FACTS).claims)
