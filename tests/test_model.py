"""Tests for the model layer with a fake client (AC-010, AC-011, AC-014, AC-019).

The reply in fixtures/sample_reply.json is written by hand in the shape the model returns. It
stands in for a recording so the full nine claim count can be pinned without a network.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

from vouch.check import check
from vouch.facts import parse_facts
from vouch.model import INSTRUCTION, DeepSeekProse, build_prompt

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = Path(__file__).parents[1] / "samples"
DRAFT = (SAMPLES / "draft.txt").read_text(encoding="utf-8")
FACTS = (SAMPLES / "facts.txt").read_text(encoding="utf-8")
SHEET = parse_facts(FACTS)


class FakeClient:
    """Stands in for openai.OpenAI. Records the request and returns a canned reply."""

    def __init__(self, reply=None, error=None, finish_reason="stop"):
        self.reply, self.error, self.finish_reason = reply, error, finish_reason
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        choice = SimpleNamespace(finish_reason=self.finish_reason, message=SimpleNamespace(content=self.reply))
        return SimpleNamespace(choices=[choice])


def reply(claims):
    return json.dumps({"claims": claims})


def claim(text, state, fact_id=None, sentence="", reason="r"):
    return {"text": text, "sentence": sentence, "state": state, "fact_id": fact_id, "reason": reason}


def test_prompt_holds_only_the_instruction_the_sheet_and_the_draft():
    system, user = build_prompt(DRAFT, SHEET)
    assert system == INSTRUCTION
    sheet_lines = "\n".join(f"{f.id} {f.label}: {f.value}" for f in SHEET.facts)
    assert user == "FACT SHEET\n" + sheet_lines + "\n\nDRAFT\n" + DRAFT


def test_request_carries_the_draft_only_to_the_configured_model():
    fake = FakeClient(reply=reply([]))
    DeepSeekProse(client=fake).check(DRAFT, SHEET)
    (call,) = fake.calls
    assert call["messages"] == [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": build_prompt(DRAFT, SHEET)[1]},
    ]
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0


def test_two_prose_claims_in_one_sentence_are_both_supported():
    sentence = "Falcon Pay is headquartered in Dubai and led by CEO Layla Haddad."
    fake = FakeClient(reply=reply([
        claim("headquartered in Dubai", "supported", "F6", sentence),
        claim("led by CEO Layla Haddad", "supported", "F4", sentence),
    ]))
    r = DeepSeekProse(client=fake).check(sentence, SHEET)
    assert [(c.state, c.fact_id) for c in r.claims] == [("supported", "F6"), ("supported", "F4")]
    assert [sentence[c.start : c.end] for c in r.claims] == ["headquartered in Dubai", "led by CEO Layla Haddad"]


def test_citation_of_a_fact_that_does_not_exist_is_downgraded():
    fake = FakeClient(reply=reply([claim("headquartered in Dubai", "supported", "F9")]))
    r = DeepSeekProse(client=fake).check("It is headquartered in Dubai.", SHEET)
    c = r.claims[0]
    assert (c.state, c.fact_id, c.reason) == ("unsupported", None, "Model cited F9 which does not exist")
    assert "model cited F9 which does not exist" in r.warnings


def test_supported_without_any_citation_is_downgraded():
    fake = FakeClient(reply=reply([claim("headquartered in Dubai", "supported", None)]))
    r = DeepSeekProse(client=fake).check("It is headquartered in Dubai.", SHEET)
    assert r.claims[0].state == "unsupported"


def test_made_up_state_is_treated_as_unsupported():
    fake = FakeClient(reply=reply([claim("headquartered in Dubai", "verified", "F6")]))
    r = DeepSeekProse(client=fake).check("It is headquartered in Dubai.", SHEET)
    assert (r.claims[0].state, r.claims[0].fact_id) == ("unsupported", None)
    assert r.warnings[0].startswith("model state 'verified'")


def test_span_not_in_the_draft_is_dropped_with_a_warning():
    fake = FakeClient(reply=reply([claim("based in Abu Dhabi", "supported", "F6")]))
    r = DeepSeekProse(client=fake).check("It is headquartered in Dubai.", SHEET)
    assert r.claims == []
    assert r.warnings == ["model span 'based in Abu Dhabi' not found in draft, dropped"]


def test_sentence_disambiguates_a_repeated_phrase():
    body = "Falcon Pay Closes Series A\n\nIt has closed a Series A funding round."
    sentence = "It has closed a Series A funding round."
    fake = FakeClient(reply=reply([claim("Series A", "supported", "F2", sentence)]))
    c = DeepSeekProse(client=fake).check(body, SHEET).claims[0]
    assert c.start == body.index(sentence) + sentence.index("Series A")


def test_timeout_degrades_with_the_reason():
    err = openai.APITimeoutError(request=httpx.Request("POST", "https://api.deepseek.com"))
    r = DeepSeekProse(client=FakeClient(error=err)).check(DRAFT, SHEET)
    assert r.error == "model timed out after 5 s"
    assert r.claims == []


def test_missing_key_degrades_and_names_the_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    r = DeepSeekProse().check(DRAFT, SHEET)
    assert r.error == "DEEPSEEK_API_KEY is not set"
    assert r.claims == []


def test_malformed_json_degrades():
    r = DeepSeekProse(client=FakeClient(reply="{not json")).check(DRAFT, SHEET)
    assert r.error == "model returned malformed JSON"


def test_wrong_shape_degrades():
    r = DeepSeekProse(client=FakeClient(reply='{"answer": "yes"}')).check(DRAFT, SHEET)
    assert r.error == "model returned malformed JSON"


def test_content_filter_degrades():
    r = DeepSeekProse(client=FakeClient(reply="{}", finish_reason="content_filter")).check(DRAFT, SHEET)
    assert r.error == "model declined the request"


@pytest.fixture
def sample_prose():
    return DeepSeekProse(client=FakeClient(reply=(FIXTURES / "sample_reply.json").read_text()))


def test_sample_has_nine_claims_with_one_error_per_state(sample_prose):
    r = check(DRAFT, FACTS, sample_prose)
    assert r.summary == {"checked": 9, "supported": 6, "rounded_up": 1, "contradicted": 1, "unsupported": 1}
    assert r.model_used is True
    assert r.approvable is False
    for c in r.claims:
        assert DRAFT[c.start : c.end] == c.text


def test_fixing_the_year_removes_the_red_but_not_the_orange(sample_prose):
    r = check(DRAFT.replace("2018", "2019"), FACTS, sample_prose)
    assert r.summary["contradicted"] == 0
    assert r.summary["rounded_up"] == 1
    assert r.approvable is False


def test_fixing_both_numbers_makes_the_sample_approvable(sample_prose):
    fixed = DRAFT.replace("2018", "2019").replace("$13 million", "$12.4 million")
    r = check(fixed, FACTS, sample_prose)
    assert r.summary["unsupported"] == 1
    assert r.approvable is True
