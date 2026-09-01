"""Score the numeric layer and the model layer against the labelled cases in evals/cases.

The numeric score gates CI: anything under 100 percent recall exits non-zero (AC-021). The
model scores are printed and do not gate. Without an API key the model layer is
skipped and says so.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

from vouch.check import check
from vouch.claims import STATES
from vouch.config import API_KEY_ENV

CASES = Path(__file__).parent / "cases"


def load_cases(layer: str) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if c["layer"] == layer]


def _same_span(predicted: str, expected: str) -> bool:
    # The model may quote a little more or less than the label. Either containing the other
    # counts as the same claim. State still has to match exactly.
    return expected in predicted or predicted in expected


def score(cases: list[dict], prose_checker=None, source: str = "numeric") -> tuple[Counter, Counter, Counter, list[str]]:
    tp, fp, fn = Counter(), Counter(), Counter()
    misses: list[str] = []
    for case in cases:
        result = check(case["draft"], case["facts"], prose_checker)
        predicted = [c for c in result.claims if c.source == source]
        unmatched = list(predicted)
        for exp in case["expected"]:
            hit = next((p for p in unmatched if _same_span(p.text, exp["text"]) and p.state == exp["state"]), None)
            if hit:
                tp[exp["state"]] += 1
                unmatched.remove(hit)
            else:
                fn[exp["state"]] += 1
                got = next((p.state for p in predicted if _same_span(p.text, exp["text"])), "nothing")
                misses.append(f"  {case['name']}: expected '{exp['text']}' {exp['state']}, got {got}")
        for p in unmatched:
            fp[p.state] += 1
            misses.append(f"  {case['name']}: unexpected '{p.text}' {p.state}")
    return tp, fp, fn, misses


def _pct(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{100 * num / den:.1f}%"


def main() -> int:
    numeric = load_cases("numeric")
    tp, fp, fn, misses = score(numeric)
    hits, total = sum(tp.values()), sum(tp.values()) + sum(fn.values())
    print(f"numeric layer: {len(numeric)} cases, recall {_pct(hits, total)} ({hits}/{total}), false positives {sum(fp.values())}")
    if misses:
        print(*misses, sep="\n")

    model_cases = load_cases("model")
    if not os.environ.get(API_KEY_ENV):
        print(f"model layer: skipped, {len(model_cases)} cases need {API_KEY_ENV}")
    else:
        from vouch.model import DeepSeekProse

        tp, fp, fn, misses = score(model_cases, DeepSeekProse(), source="model")
        print(f"model layer: {len(model_cases)} cases")
        for state in STATES:
            if state == "rounded_up":
                continue
            print(f"  {state:<13} precision {_pct(tp[state], tp[state] + fp[state]):>6}   recall {_pct(tp[state], tp[state] + fn[state]):>6}")
        if misses:
            print(*misses, sep="\n")

    # The gate. Numbers are checked by code, so anything short of every case is a bug.
    if hits < total:
        print("FAIL: numeric layer recall is below 100 percent")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
