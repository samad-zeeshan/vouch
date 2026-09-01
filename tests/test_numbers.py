"""Tests for number extraction from a draft (AC-003)."""

import pytest

from vouch.numbers import extract_numbers


@pytest.mark.parametrize(
    "text, value, kind",
    [
        ("$12.4 million", 12_400_000, "money"),
        ("$13M", 13_000_000, "money"),
        ("38,000", 38_000, "count"),
        ("2019", 2019, "year"),
        ("40%", 40, "percent"),
        ("40 percent", 40, "percent"),
        ("1.2bn", 1_200_000_000, "count"),
    ],
)
def test_each_form_is_extracted_with_value_and_span(text, value, kind):
    draft = f"The company reported {text} last year."
    found = extract_numbers(draft)
    assert len(found) == 1
    n = found[0]
    assert n.value == value
    assert n.kind == kind
    assert draft[n.start : n.end] == n.text == text


def test_hedge_word_is_part_of_the_span():
    draft = "It serves over 38,000 customers and more than 40 markets."
    found = extract_numbers(draft)
    assert [n.text for n in found] == ["over 38,000", "more than 40"]
    assert found[0].hedge == "over"
    assert draft[found[0].start : found[0].end] == "over 38,000"


def test_digits_inside_words_are_not_numbers():
    assert extract_numbers("A B2B platform built for 5G and COVID19 recovery") == []


def test_phone_numbers_and_urls_are_not_numbers():
    draft = "Call +971 4 123 4567 or visit https://falconpay.com/2019/launch or 800-FALCON."
    assert extract_numbers(draft) == []


def test_email_local_parts_are_not_numbers():
    assert extract_numbers("Write to press2024@falconpay.com today.") == []


def test_spans_survive_characters_outside_the_basic_plane():
    # The page highlights by offset, so offsets must count code points the same way Python does.
    draft = "Falcon Pay \U0001F680 raised $13M."
    n = extract_numbers(draft)[0]
    assert draft[n.start : n.end] == "$13M"


def test_years_need_exactly_four_digits_in_range():
    found = extract_numbers("In 2019 there were 1,900 staff and version 1.2.3 shipped.")
    assert [(n.text, n.kind) for n in found] == [("2019", "year"), ("1,900", "count")]
