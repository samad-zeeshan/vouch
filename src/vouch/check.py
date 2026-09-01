"""Run one check: numbers by code, prose by the model, merged into the API response."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from vouch.claims import STATES, Claim
from vouch.config import check_quotes
from vouch.facts import FactSheet, parse_facts
from vouch.numeric import judge_numbers
from vouch.quotes import judge_quotes


@dataclass
class ProseResult:
    claims: list[Claim] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class ProseChecker(Protocol):
    def check(self, draft: str, sheet: FactSheet) -> ProseResult: ...


@dataclass
class CheckResult:
    claims: list[Claim]
    model_used: bool
    warnings: list[str]

    @property
    def summary(self) -> dict:
        counts = Counter(c.state for c in self.claims)
        return {"checked": len(self.claims), **{s: counts.get(s, 0) for s in STATES}}

    @property
    def approvable(self) -> bool:
        return approvable(self.claims, self.model_used)

    def to_dict(self) -> dict:
        return {
            "claims": [c.to_dict() for c in self.claims],
            "summary": self.summary,
            "approvable": self.approvable,
            "model_used": self.model_used,
            "warnings": self.warnings,
        }


def approvable(claims: list[Claim], model_used: bool) -> bool:
    # A check the model never ran is not a check (AC-014).
    if not model_used:
        return False
    if any(c.state in ("contradicted", "rounded_up") for c in claims):
        return False
    # An unapproved number is the exact thing the goal forbids, so it blocks too. Unsupported
    # prose only warns (A3), because a deliberate boast is sometimes the point.
    return not any(c.state == "unsupported" and c.source == "numeric" for c in claims)


def merge(numeric: list[Claim], prose: list[Claim], warnings: list[str]) -> list[Claim]:
    kept = list(numeric)
    for p in prose:
        # The code has already ruled on anything overlapping a number, so the model's
        # opinion on that span is dropped, whatever it was (AC-009).
        if any(p.start < n.end and n.start < p.end for n in numeric):
            warnings.append(f"model verdict on '{p.text}' discarded (numeric)")
            continue
        kept.append(p)
    return sorted(kept, key=lambda c: c.start)


def check(draft: str, facts: str, prose_checker: ProseChecker | None = None) -> CheckResult:
    sheet = parse_facts(facts)
    warnings = list(sheet.warnings)
    numeric = judge_numbers(draft, sheet)
    # Quote verdicts come from code too, so they sit with the numeric ones and outrank the model.
    if check_quotes():
        numeric = sorted(numeric + judge_quotes(draft, sheet), key=lambda c: c.start)

    if prose_checker is None:
        warnings.append("Prose claims were not checked: model is off")
        return CheckResult(numeric, False, warnings)

    result = prose_checker.check(draft, sheet)
    warnings.extend(result.warnings)
    if result.error:
        warnings.append(f"Prose claims were not checked: {result.error}")
        return CheckResult(numeric, False, warnings)
    return CheckResult(merge(numeric, result.claims, warnings), True, warnings)
