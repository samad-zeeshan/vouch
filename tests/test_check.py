"""Tests for merging, the approve rule, and the model-off path (AC-009, AC-014, AC-017)."""

from vouch.check import ProseResult, approvable, check, merge
from vouch.claims import Claim

FACTS = "Funding round: $12.4 million\nFounded: 2019\nHeadquarters: Dubai\n"
DRAFT = "Falcon Pay, founded in 2018 in Dubai, raised $13 million."


class FakeProse:
    def __init__(self, claims=(), error=None, warnings=()):
        self.result = ProseResult(list(claims), list(warnings), error)
        self.calls = []

    def check(self, draft, sheet):
        self.calls.append((draft, [f.id for f in sheet.facts]))
        return self.result


def prose(text, state, fact_id=None, reason="r"):
    start = DRAFT.index(text)
    return Claim(text, start, start + len(text), state, reason, fact_id, source="model")


def test_model_off_reports_numbers_only_and_cannot_approve():
    r = check("Founded in 2019.", "Founded: 2019\n")
    assert r.model_used is False
    assert r.approvable is False
    assert r.summary == {"checked": 1, "supported": 1, "rounded_up": 0, "contradicted": 0, "unsupported": 0}
    assert r.warnings == ["Prose claims were not checked: model is off"]


def test_numeric_verdict_is_final_over_the_model():
    fake = FakeProse([prose("$13 million", "supported", "F1", "looks fine")])
    r = check(DRAFT, FACTS, fake)
    states = {c.text: c.state for c in r.claims}
    assert states["$13 million"] == "rounded_up"
    assert "model verdict on '$13 million' discarded (numeric)" in r.warnings


def test_model_claim_partly_overlapping_a_number_is_also_discarded():
    fake = FakeProse([prose("founded in 2018", "supported", "F2")])
    r = check(DRAFT, FACTS, fake)
    assert [c.text for c in r.claims if c.source == "model"] == []


def test_prose_claims_are_kept_and_sorted_by_position():
    fake = FakeProse([prose("Dubai", "supported", "F3")])
    r = check(DRAFT, FACTS, fake)
    assert [c.text for c in r.claims] == ["2018", "Dubai", "$13 million"]
    assert r.model_used is True


def test_model_failure_degrades_and_never_passes():
    fake = FakeProse(error="timed out after 5 s")
    r = check("Falcon Pay is based in Dubai.", FACTS, fake)
    assert r.model_used is False
    assert r.approvable is False
    assert r.claims == []
    assert "Prose claims were not checked: timed out after 5 s" in r.warnings


def test_sheet_warnings_reach_the_response():
    r = check("x", "no colon here\nFounded: 2019\n")
    assert r.warnings[0].startswith("1 fact sheet line ignored (no colon)")


def test_approvable_rule():
    ok = Claim("a", 0, 1, "supported", "r")
    warn = Claim("b", 0, 1, "unsupported", "r")
    assert approvable([ok, warn], model_used=True) is True
    assert approvable([ok, warn], model_used=False) is False
    for state in ("rounded_up", "contradicted"):
        assert approvable([ok, Claim("c", 0, 1, state, "r")], model_used=True) is False


def test_merge_leaves_numeric_claims_untouched():
    n = Claim("2018", 0, 4, "contradicted", "r", "F2")
    w = []
    assert merge([n], [], w) == [n] and w == []
