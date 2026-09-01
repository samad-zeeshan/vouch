"""Tests for the fact sheet parser (AC-001, AC-002)."""

from vouch.facts import parse_facts

SIX_LINES = """Company: Falcon Pay
Funding round: $12.4 million, Series A

Founded: 2019
CEO: Layla Haddad
Customers: 38,412
Headquarters: Dubai
"""


def test_one_fact_per_line_in_file_order():
    sheet = parse_facts(SIX_LINES)
    assert [f.id for f in sheet.facts] == ["F1", "F2", "F3", "F4", "F5", "F6"]
    assert sheet.facts[1].label == "Funding round"
    assert sheet.facts[1].value == "$12.4 million, Series A"
    assert sheet.warnings == []


def test_blank_lines_trailing_spaces_and_crlf_do_not_change_result():
    messy = SIX_LINES.replace("\n", "   \r\n").replace("Founded", "  Founded")
    assert parse_facts(messy).facts == parse_facts(SIX_LINES).facts


def test_line_without_colon_is_ignored_and_counted():
    sheet = parse_facts("Company: Falcon Pay\nThis line has no colon\nFounded: 2019\n")
    assert [f.label for f in sheet.facts] == ["Company", "Founded"]
    assert sheet.warnings == ["1 fact sheet line ignored (no colon): This line has no colon"]


def test_two_bad_lines_are_reported_together():
    sheet = parse_facts("just words\nCEO: Layla Haddad\nmore words\n")
    assert len(sheet.facts) == 1
    assert sheet.warnings == ["2 fact sheet lines ignored (no colon): just words; more words"]


def test_value_may_itself_contain_a_colon():
    sheet = parse_facts("Website: https://falconpay.com\n")
    assert sheet.facts[0].label == "Website"
    assert sheet.facts[0].value == "https://falconpay.com"


def test_empty_sheet_gives_no_facts_and_no_warnings():
    sheet = parse_facts("")
    assert sheet.facts == [] and sheet.warnings == []
