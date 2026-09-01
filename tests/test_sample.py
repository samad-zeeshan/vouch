"""The shipped sample plants exactly one mistake per colour (AC-019).

With the model off only the three numeric claims are visible. The full nine claim count is
asserted in test_model.py with a recorded model reply.
"""

from pathlib import Path

from vouch.check import check

SAMPLES = Path(__file__).parents[1] / "samples"
DRAFT = (SAMPLES / "draft.txt").read_text(encoding="utf-8")
FACTS = (SAMPLES / "facts.txt").read_text(encoding="utf-8")


def test_sample_numbers_plant_one_round_up_one_contradiction_and_one_match():
    r = check(DRAFT, FACTS)
    assert r.summary == {"checked": 3, "supported": 1, "rounded_up": 1, "contradicted": 1, "unsupported": 0}
    by_text = {c.text: (c.state, c.fact_id) for c in r.claims}
    assert by_text["$13 million"] == ("rounded_up", "F2")
    assert by_text["2018"] == ("contradicted", "F3")
    assert by_text["over 38,000"] == ("supported", "F5")


def test_sample_sheet_parses_cleanly():
    r = check(DRAFT, FACTS)
    assert not any("ignored" in w for w in r.warnings)
