# Vouch

AI writes a press release in ten seconds and gets the funding number wrong. Vouch catches it before the client does.

## Run it

```
uv run vouch
```

Open http://localhost:8000. The sample draft and fact sheet are already loaded. Click Check.

No API key? It still works. Numbers get checked, a banner tells you prose was not, and Approve stays locked. Set `DEEPSEEK_API_KEY` to check everything.

## The problem

Ask any model to write a press release and it will hand you something fluent, confident, and slightly wrong. A funding round quietly rounds from $12.4 million up to $13 million. A founding year drifts by one. A "fastest-growing fintech in the Gulf" appears that nobody approved. Each mistake is small. Each one is the kind a client notices after it is published.

PR teams catch these by reading the draft against the client's fact sheet, line by line, twice. Vouch does that read in seconds and refuses to let an unapproved number through.

## What happens when you click Check

You give Vouch two things. The draft on the left. The client's approved fact sheet on the right, one fact per line, written as `Label: value`.

Every claim in the draft that the sheet could confirm or deny gets a colour, in place:

- **green, supported.** The sheet backs it.
- **orange, rounded up.** A number is bigger than the sheet says, within 25 percent. Rounding up is a change to the number, so it blocks.
- **red, contradicted.** It clashes with a fact. A wrong year. A wrong CEO. A number that disagrees with its own labelled fact.
- **dashed underline, unsupported.** The sheet says nothing about it.

Hover any colour and you get one plain sentence saying why. Fix the draft, click Check again, watch the red disappear. Approve only unlocks when nothing is red or orange and no unapproved number remains.

Under the hood there are two layers, and they are not equals.

**Numbers are checked by code.** Money, percentages, years and counts are pulled out of the draft with their exact positions and compared in plain Python. Code cannot hallucinate, so on numbers its verdict is final.

**Prose is checked by a model.** Names, titles, places and boasts go to DeepSeek along with the sheet and nothing else. Then its answer is checked. A "supported" verdict must cite a fact that actually exists on the sheet. The span it quotes must actually appear in the draft. Fail either check and the claim is downgraded, with a warning that says so.

**When they disagree, code wins.** And when the model times out, refuses, or returns broken JSON, the numbers still show, the page says prose was not checked, and Approve stays locked. Failure never looks like a pass.

## The numbers, as measured

Run `uv run python -m evals` and you get these. Nothing below is rounded or promised.

| Layer | Cases | Result |
| --- | --- | --- |
| Numeric | 13 | recall 100.0% (14/14), 0 false positives. CI fails the build below 100. |
| Model, supported | 15 total | precision 71.4%, recall 100.0% |
| Model, contradicted | | precision 71.4%, recall 100.0% |
| Model, unsupported | | precision 60.0%, recall 75.0% |

The number that matters most is contradicted recall. A missed lie is the one unforgivable error here, so the prompt went through three measured iterations until it reached 100 percent, and the cost landed on precision. That trade is deliberate. Over-flagging means a human reviews an extra highlight. Under-flagging means a lie ships.

The eval script prints every miss instead of hiding them. 64 tests run offline against a fake model, on every push.

## Small on purpose

No accounts, no saving, no file upload, no web lookups. The fact sheet is the only source of truth. Vouch reports and the human edits, it never rewrites. Quote checking exists behind `CHECK_QUOTES=on`, off by default, shipped dark on purpose.

The spec came first. [SPEC.md](SPEC.md) holds 23 acceptance criteria, written before any code, and the commit history follows its build order. Revision 2 came out of live testing, when a $13 million figure against a $22 million fact sheet line slipped through as a dashed underline. Now it goes red and blocks.

## Useful switches

| Variable | Does |
| --- | --- |
| `DEEPSEEK_API_KEY` | enables the prose layer |
| `MODEL=off` | numbers only, fully offline |
| `VOUCH_MODEL` | model id, default `deepseek-chat` |
| `CHECK_QUOTES=on` | the dark quote check |

Tests: `uv run pytest`. Evals: `uv run python -m evals`.

Python 3.12, FastAPI, DeepSeek through its OpenAI-compatible API, one HTML page with vanilla JS, pytest, GitHub Actions. No database, no front-end framework, no build step.
