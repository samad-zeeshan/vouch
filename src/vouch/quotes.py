"""Match quoted speech in the draft against Quote: lines on the sheet.

Dark feature. Off unless CHECK_QUOTES=on. The check works and is tested, the page does nothing
special with it yet.
"""

import re

from vouch.claims import Claim
from vouch.facts import FactSheet

# Straight or curly quotes, at least twenty characters inside so "Series A" style mentions in
# quotes are not mistaken for speech.
_QUOTED = re.compile(r"[\"“]([^\"”]{20,}?)[\"”]")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def judge_quotes(draft: str, sheet: FactSheet) -> list[Claim]:
    approved = [f for f in sheet.facts if f.label.strip().lower() == "quote"]
    claims = []
    for m in _QUOTED.finditer(draft):
        text = m.group(1)
        match = next((f for f in approved if _norm(text) in _norm(f.value) or _norm(f.value) in _norm(text)), None)
        if match:
            claims.append(Claim(text, m.start(1), m.end(1), "supported", f"Matches {match.id}.", match.id, source="quote"))
        else:
            claims.append(Claim(text, m.start(1), m.end(1), "unsupported", "Quote not on the approved sheet", None, source="quote"))
    return claims
