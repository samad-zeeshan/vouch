"""Judge every number in the draft against the numbers on the fact sheet.

Code only. The model never touches these verdicts (AC-009).
"""

import math
import re
from dataclasses import dataclass

from vouch.claims import Claim
from vouch.facts import Fact, FactSheet
from vouch.numbers import Number, extract_numbers

# A draft number this far above the sheet is a round-up, not a different number (A2).
TOLERANCE = 0.25

_CURRENCY = re.compile(r"^(?:[$£€]|AED\s?|USD\s?)")
_STOPWORDS = {"the", "and", "of", "in", "at", "for", "per", "total"}


@dataclass(frozen=True)
class SheetNumber:
    fact: Fact
    number: Number


def sheet_numbers(sheet: FactSheet) -> list[SheetNumber]:
    return [SheetNumber(f, n) for f in sheet.facts for n in extract_numbers(f.value)]


def fmt(n: Number) -> str:
    v = n.value
    if n.kind == "year":
        return str(int(v))
    if n.kind == "percent":
        return f"{v:g}%"
    # Press releases write "$12.4M", not "$12,400,000", so reasons do the same.
    if v >= 1e9:
        body = f"{v / 1e9:g}B"
    elif v >= 1e6:
        body = f"{v / 1e6:g}M"
    else:
        body = f"{v:,.0f}" if v == int(v) else f"{v:,}"
    cur = _CURRENCY.match(n.text)
    return (cur.group().strip() if cur else "") + body


def _compatible(a: Number, b: Number) -> bool:
    # Years and percentages only ever match their own kind. Money and plain counts are allowed
    # to match each other because sheets often drop the currency sign.
    if "year" in (a.kind, b.kind) or "percent" in (a.kind, b.kind):
        return a.kind == b.kind
    return True


def _sentence(draft: str, start: int, end: int) -> str:
    left = max(draft.rfind(c, 0, start) for c in ".!?\n")
    rights = [i for i in (draft.find(c, end) for c in ".!?\n") if i != -1]
    return draft[left + 1 : min(rights) if rights else len(draft)]


def _label_in(fact: Fact, sentence: str) -> bool:
    words = {w for w in re.findall(r"[a-z]+", fact.label.lower()) if w not in _STOPWORDS}
    return any(w in sentence.lower() for w in words)


def _verdict(d: Number, cands: list[SheetNumber], sentence: str) -> Claim:
    def ranked(items: list[SheetNumber]) -> list[SheetNumber]:
        # Value first, then the label in the same sentence breaks ties (R1). This is the weak
        # link the spec names, so keep the rule small enough to explain.
        return sorted(
            items,
            key=lambda s: (
                not _label_in(s.fact, sentence),
                abs(d.value - s.number.value) / max(s.number.value, 1),
            ),
        )

    def claim(state: str, reason: str, fact: Fact | None = None) -> Claim:
        return Claim(d.text, d.start, d.end, state, reason, fact.id if fact else None)

    exact = [c for c in cands if math.isclose(c.number.value, d.value)]
    if exact:
        best = ranked(exact)[0]
        return claim("supported", f"Matches {best.fact.id}.", best.fact)

    if d.kind == "year":
        if not cands:
            return claim("unsupported", f"No year on the sheet matches {fmt(d)}.")
        best = ranked(cands)[0]
        return claim("contradicted", f"Sheet says {fmt(best.number)}. Draft says {fmt(d)}.", best.fact)

    near = [c for c in cands if abs(d.value - c.number.value) / max(c.number.value, 1) <= TOLERANCE]
    if not near:
        # Outside tolerance usually means the sheet does not speak to this number. But when the
        # fact's own label sits in the same sentence, it does speak, and it disagrees (AC-023).
        labelled = [c for c in cands if _label_in(c.fact, sentence)]
        if labelled:
            best = ranked(labelled)[0]
            return claim("contradicted", f"Sheet says {fmt(best.number)}. Draft says {fmt(d)}.", best.fact)
        return claim("unsupported", f"No number on the sheet is within 25 percent of {fmt(d)}.")
    best = ranked(near)[0]
    if d.value > best.number.value:
        return claim(
            "rounded_up",
            f"Sheet says {fmt(best.number)}. Draft says {fmt(d)}. Rounding up is a change to the number.",
            best.fact,
        )
    shown = d.text[0].upper() + d.text[1:]
    return claim("supported", f"Sheet says {fmt(best.number)}. '{shown}' is a fair presentation.", best.fact)


def judge_numbers(draft: str, sheet: FactSheet) -> list[Claim]:
    pool = sheet_numbers(sheet)
    claims = []
    for d in extract_numbers(draft):
        cands = [s for s in pool if _compatible(d, s.number)]
        claims.append(_verdict(d, cands, _sentence(draft, d.start, d.end)))
    return claims
