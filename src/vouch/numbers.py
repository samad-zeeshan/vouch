"""Find every number in a draft, with its plain value and its exact position.

Money, percentages, years, and plain counts are told apart because they are matched differently.
"""

import re
from dataclasses import dataclass

# Order matters within the alternation: "bn" and "million" must be tried before the one letter
# forms or "1.2bn" would stop at "1.2b".
_NUMBER = re.compile(
    r"""
    (?<![\w.,])                                  # not glued to a word, decimal, or thousands group
    (?P<cur>[$£€]|AED\s?|USD\s?)?
    (?P<digits>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?
    (?:\s?(?P<unit>billion|million|thousand|bn|mn|[bmk]))?
    (?P<pct>\s?(?:%|percent))?
    (?!\w|\.\d)                                  # "5G" and "1.2.3" are not numbers
    """,
    re.IGNORECASE | re.VERBOSE,
)

_HEDGE = re.compile(
    r"(?:\b(?:over|more than|at least|nearly|almost|about|around|approximately|roughly|close to|up to|some)\s+)$",
    re.IGNORECASE,
)

# Anything matched here is blanked out before the number search. Blanking keeps the string the
# same length, so every offset still points at the original draft.
_NOISE = [
    re.compile(r"https?://\S+|www\.\S+|\b[\w.-]+\.(?:com|net|org|io|ae|co|uk)\b\S*", re.I),
    re.compile(r"\S+@\S+"),
    re.compile(r"\+?\d[\d\s().-]{6,}\d"),
    re.compile(r"\b\d{3}-[A-Z]{3,}\b"),
]

_UNITS = {
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mn": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}


@dataclass(frozen=True)
class Number:
    text: str
    start: int
    end: int
    value: float
    kind: str
    hedge: str | None = None


def _blank_noise(text: str) -> str:
    for pattern in _NOISE:
        text = pattern.sub(lambda m: " " * len(m.group()), text)
    return text


def extract_numbers(draft: str) -> list[Number]:
    scan = _blank_noise(draft)
    found: list[Number] = []
    for m in _NUMBER.finditer(scan):
        digits, frac = m.group("digits"), m.group("frac") or ""
        value = float(digits.replace(",", "") + frac)
        unit = (m.group("unit") or "").lower()
        value *= _UNITS.get(unit, 1)

        if m.group("pct"):
            kind = "percent"
        elif m.group("cur"):
            kind = "money"
        # A bare four digit integer in a plausible range reads as a year to a person, so it is
        # one here too. "1,900" has a comma and stays a count.
        elif not unit and not frac and "," not in digits and len(digits) == 4 and 1900 <= value <= 2100:
            kind = "year"
        else:
            kind = "count"

        start, end = m.start(), m.end()
        hedge = _HEDGE.search(scan[:start])
        if hedge:
            start = hedge.start()
        # Slice the original draft, not the blanked copy, so text is exactly what the writer typed.
        found.append(Number(draft[start:end], start, end, value, kind,
                            hedge.group().strip().lower() if hedge else None))
    return found
