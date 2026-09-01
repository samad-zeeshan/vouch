"""Tests for numeric verdicts (AC-004 to AC-008)."""

from vouch.facts import parse_facts
from vouch.numeric import judge_numbers

SHEET = parse_facts(
    "Company: Falcon Pay\n"
    "Funding round: $12.4 million, Series A\n"
    "Founded: 2019\n"
    "CEO: Layla Haddad\n"
    "Customers: 38,412\n"
    "Headquarters: Dubai\n"
)


def one(draft, sheet=SHEET):
    claims = judge_numbers(draft, sheet)
    assert len(claims) == 1, claims
    return claims[0]


def test_exact_match_is_supported():
    c = one("Falcon Pay closed a $12.4 million round.")
    assert (c.state, c.fact_id, c.reason) == ("supported", "F2", "Matches F2.")


def test_rounding_up_is_caught():
    c = one("Falcon Pay closed a $13 million round.")
    assert c.state == "rounded_up"
    assert c.fact_id == "F2"
    assert c.reason == "Sheet says $12.4M. Draft says $13M. Rounding up is a change to the number."


def test_rounding_down_with_a_hedge_is_supported_with_a_note():
    c = one("It serves over 38,000 customers.")
    assert c.state == "supported"
    assert c.reason == "Sheet says 38,412. 'Over 38,000' is a fair presentation."


def test_years_must_match_exactly():
    c = one("Founded in 2018, Falcon Pay grew fast.")
    assert (c.state, c.fact_id, c.reason) == ("contradicted", "F3", "Sheet says 2019. Draft says 2018.")


def test_years_get_no_tolerance_even_when_close():
    assert one("Founded in 2020.").state == "contradicted"


def test_number_clashing_with_a_labelled_fact_is_contradicted():
    sheet = parse_facts("Funding round: $22 million\n")
    c = one("Falcon Pay closed a $13 million funding round.", sheet)
    assert (c.state, c.fact_id) == ("contradicted", "F1")
    assert c.reason == "Sheet says $22M. Draft says $13M."


def test_number_with_nothing_close_is_unsupported():
    c = one("It has 900 employees.")
    assert c.state == "unsupported"
    assert c.fact_id is None
    assert c.reason == "No number on the sheet is within 25 percent of 900."


def test_percent_never_matches_a_plain_count():
    sheet = parse_facts("Customers: 40\n")
    assert one("Growth was 40% this year.", sheet).state == "unsupported"


def test_label_in_the_sentence_breaks_a_tie_between_close_facts():
    sheet = parse_facts("Funding round: $12 million\nValuation: $13.5 million\n")
    c = one("Falcon Pay closed a $13 million funding round.", sheet)
    assert (c.state, c.fact_id) == ("rounded_up", "F1")


def test_claim_span_points_at_the_draft():
    draft = "Founded in 2018, it serves over 38,000 customers."
    for c in judge_numbers(draft, SHEET):
        assert draft[c.start : c.end] == c.text
