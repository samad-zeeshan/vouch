"""Check prose claims with the model, then check the model.

The model sees the draft and the sheet and nothing else. Every verdict it returns is re-checked
here before it can reach the page: a cited fact must exist, and a quoted span must be in the draft.
"""

import json
import os
from dataclasses import dataclass

from vouch.check import ProseResult
from vouch.claims import Claim
from vouch.config import API_BASE, API_KEY_ENV, MODEL_ID
from vouch.facts import FactSheet

INSTRUCTION = """You check a draft press release against the client's approved fact sheet.

List every claim in the draft that the fact sheet could confirm or deny: names, job titles, places, product descriptions, investors, partners, and descriptive statements such as "fastest-growing" or "the region's first".

Rules:
- Use the fact sheet as the only source of truth. Do not use anything you know from elsewhere.
- Leave numbers, money, percentages and years alone. Code checks those separately. Do not list a claim whose substance is a number.
- List every checkable claim. When the sheet says nothing about a claim, still list it, as unsupported. Staying silent about a checkable claim is always wrong.
- The first line of the draft is the headline. Take no claim from it.
- A person's job title, and which company they belong to, are claims. If the sheet says otherwise for that person, the claim is contradicted, citing that fact.
- Skip quoted speech and who said it, contact details and calls to action.
- "supported" needs a fact ID that confirms the claim. "contradicted" needs a fact ID the claim conflicts with. When no fact speaks to the claim, use "unsupported" and set fact_id to null.
- "text" is the shortest exact substring of the draft that carries the claim. "sentence" is the exact sentence it sits in, copied verbatim, so the claim can be located.
- "reason" is one plain sentence a PR consultant can read. For "unsupported", name what kind of fact is missing.

Return JSON only, in this exact shape: {"claims": [{"text": "...", "sentence": "...", "state": "supported" | "contradicted" | "unsupported", "fact_id": "F1" | null, "reason": "..."}]}"""

MODEL_STATES = ("supported", "contradicted", "unsupported")
TIMEOUT_SECONDS = 5.0


def build_prompt(draft: str, sheet: FactSheet) -> tuple[str, str]:
    lines = [f"{f.id} {f.label}: {f.value}" for f in sheet.facts]
    user = "FACT SHEET\n" + "\n".join(lines) + "\n\nDRAFT\n" + draft
    return INSTRUCTION, user


def _locate(draft: str, text: str, sentence: str) -> int:
    # The sentence narrows the search so "Series A" in the body is not mistaken for the one in
    # the headline. If the model misquoted the sentence, fall back to the first occurrence.
    at = draft.find(sentence) if sentence else -1
    if at != -1:
        inner = draft.find(text, at, at + len(sentence))
        if inner != -1:
            return inner
    return draft.find(text)


def to_claims(payload: dict, draft: str, sheet: FactSheet, warnings: list[str]) -> list[Claim]:
    claims = []
    for item in payload["claims"]:
        text, state, fact_id, reason = item["text"], item["state"], item.get("fact_id"), item["reason"]
        start = _locate(draft, text, item.get("sentence", ""))
        if start == -1:
            warnings.append(f"model span '{text}' not found in draft, dropped")
            continue
        # JSON mode guarantees valid JSON, not a valid state. Anything off the list is treated
        # as the model not knowing, which is what unsupported means.
        if state not in MODEL_STATES:
            warnings.append(f"model state '{state}' on '{text}' is not a state, treated as unsupported")
            state = "unsupported"
        # A verdict is only as good as its citation (AC-011). An ID that is not on the sheet
        # means the model made something up, so the claim falls to unsupported.
        if state != "unsupported" and (not fact_id or sheet.by_id(fact_id) is None):
            warnings.append(f"model cited {fact_id} which does not exist")
            reason, state, fact_id = f"Model cited {fact_id} which does not exist", "unsupported", None
        if state == "unsupported":
            fact_id = None
        claims.append(Claim(text, start, start + len(text), state, reason, fact_id, source="model"))
    return claims


@dataclass
class DeepSeekProse:
    client: object | None = None

    def _client(self):
        if self.client is None:
            from openai import OpenAI

            # DeepSeek speaks the OpenAI wire format, so the official openai client with a
            # different base URL is the whole integration. One retry after a 5 second timeout
            # is the entire retry budget (spec, other rules).
            self.client = OpenAI(
                api_key=os.environ.get(API_KEY_ENV, ""),
                base_url=API_BASE,
                timeout=TIMEOUT_SECONDS,
                max_retries=1,
            )
        return self.client

    def check(self, draft: str, sheet: FactSheet) -> ProseResult:
        import openai

        system, user = build_prompt(draft, sheet)
        # The SDK refuses to build a client without a key. Say which key, so the banner on
        # the page tells the person exactly what to set.
        if self.client is None and not os.environ.get(API_KEY_ENV):
            return ProseResult(error=f"{API_KEY_ENV} is not set")
        try:
            response = self._client().chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                # JSON mode only holds when the prompt itself asks for JSON, which the
                # instruction does. Temperature 0 so the same draft gets the same verdicts.
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=4096,
            )
        except openai.APITimeoutError:
            return ProseResult(error=f"model timed out after {TIMEOUT_SECONDS:g} s")
        # Every other failure degrades the same way (AC-014). OpenAIError is the SDK's root
        # class, so this also covers client construction, not only the request.
        except openai.OpenAIError as e:
            return ProseResult(error=f"model call failed ({type(e).__name__})")

        choice = response.choices[0]
        if choice.finish_reason == "content_filter":
            return ProseResult(error="model declined the request")
        try:
            payload = json.loads(choice.message.content or "")
            warnings: list[str] = []
            claims = to_claims(payload, draft, sheet, warnings)
        except (ValueError, KeyError, TypeError, AttributeError):
            return ProseResult(error="model returned malformed JSON")
        return ProseResult(claims, warnings)
