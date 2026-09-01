# Vouch

Vouch is a check that sits between "the AI wrote the press release" and "the client sees it".

You paste the draft. You paste the client's approved fact sheet. You click Check. Every claim
in the draft that can be checked gets a colour: green if the sheet backs it up, orange if a
number was rounded up, red if it contradicts the sheet, and a dashed underline if the sheet
says nothing about it. Hover any colour and you get a one-line reason. The Approve button
stays off until there is nothing red or orange left.

This spec was written before any code. Every acceptance criterion below is something you can
watch happen, or watch fail. Revision 1, 2026-09-01.

## Goal

A PR consultant should be able to confirm, in under a minute and without reading the draft
twice, that an AI-written release contains no number, date, or name the client did not
approve.

## Who uses it

- The PR consultant. They paste, click, read the colours, fix the draft, and click again.
  They never see a fact ID, a prompt, or raw JSON.
- The person reviewing this repo. They clone it, run one command, and watch the sample draft
  light up.

## What is in

- One page. Two text boxes (the draft and the fact sheet), a Check button, an Approve button.
- Numbers, money, percentages, and years are checked by code. No AI involved.
- Everything else (names, job titles, places, descriptive statements) is checked by the model,
  with strict limits on what it is allowed to say.
- Highlights appear in the draft itself. Hover shows the reason. A summary line gives the
  counts.
- A sample draft and sample fact sheet ship with the repo. The sample has exactly one planted
  mistake for each colour.
- Tests for the code layer, an eval set for the model layer, and CI that runs both.

## What is out (on purpose)

- Accounts, saving, history, file upload, PDF or Word input, checking many documents at once.
- Looking things up on the web. The fact sheet is the only source of truth.
- Rewriting the draft. Vouch reports; the human edits.
- Checking quotes. This is built behind a switch that is off by default. See "Dark features".

## Assumptions

These need confirming with a real PR team. They cannot be worked out from the code.

- A1. Clients hand over an approved fact sheet as short plain lines, one fact per line.
- A2. Rounding a number up is never fine in a release. Rounding down, or hedging ("over
  38,000"), is fine and gets a note rather than a block.
- A3. A descriptive claim the sheet does not cover ("fastest-growing fintech in the Gulf") is
  a warning the consultant can approve past. Lines like that are sometimes deliberate.
- A4. Nothing in the draft is too sensitive to send to the model API.

## Words used in this spec

- **Fact sheet.** Plain text, one fact per line, written as `Label: value`. Each line becomes
  a fact with an ID (F1, F2, ...) in the order it appears. A line with no colon is skipped,
  but the skip is counted and reported.
- **Claim.** A piece of the draft that says something the fact sheet could confirm or deny.
  Contact details, calls to action, and headings are not claims.
- **The four states.** Exactly four. One colour each.
  - `supported` (green): matches a fact.
  - `rounded_up` (orange): a number in the draft is bigger than the closest number on the
    sheet, but within 25 percent of it.
  - `contradicted` (red): clashes with a fact.
  - `unsupported` (white with a dashed underline): nothing on the sheet speaks to it.
- **Numeric claim.** Any claim that contains a number (see AC-003 for what counts as a
  number). Checked by code only.
- **Prose claim.** Any other claim. Checked by the model, within the limits set by AC-010 and
  AC-011.

## What goes in and what comes out

Request: `POST /check` with `{ "draft": string, "facts": string }`.

Response:

```
{
  "claims": [
    { "text": "founded in 2018", "start": 212, "end": 227,
      "state": "contradicted", "fact_id": "F3",
      "reason": "Sheet says 2019. Draft says 2018." }
  ],
  "summary": { "checked": 9, "supported": 6, "rounded_up": 1,
               "contradicted": 1, "unsupported": 1 },
  "approvable": false,
  "model_used": true,
  "warnings": []
}
```

`start` and `end` are character positions in the draft, exactly as it was sent. That lets
the page underline the right words without having to work out the text again.

## Acceptance criteria

Everything is required unless it says "Nice to have".

### The fact sheet

**AC-001 One line becomes one fact**
- Given: a fact sheet with six `Label: value` lines and one blank line.
- Then: six facts, F1 to F6, in file order, each with its label and its raw value.
- Must not: crash or change the order because of blank lines, trailing spaces, or Windows
  line endings.
- Checked by: unit test.

**AC-002 A bad line is counted, not quietly dropped**
- Given: one line has no colon.
- Then: the response `warnings` list includes "1 fact sheet line ignored (no colon): ...".
- Must not: treat the line as a fact, or hide that it was skipped.
- Checked by: unit test.

### The code layer (numbers)

**AC-003 Numbers are found in the forms a real release uses**
- Given: a draft containing `$12.4 million`, `$13M`, `38,000`, `2019`, `40%`, `40 percent`,
  and `1.2bn`.
- Then: each one is found, given a plain value (12400000, 13000000, 38000, 2019, 40, 40,
  1200000000), and its exact position in the text.
- Must not: pick up digits inside words, phone numbers, or web addresses.
- Checked by: unit test, one case for each form.

**AC-004 An exact match is supported**
- Given: draft says `$12.4 million`; sheet says `Funding round: $12.4 million, Series A`.
- Then: `supported`, fact F2, reason "Matches F2."
- Checked by: unit test.

**AC-005 Rounding up is caught**
- Given: draft says `$13 million`; sheet says `$12.4 million`.
- Then: `rounded_up`, reason "Sheet says $12.4M. Draft says $13M. Rounding up is a change
  to the number."
- Must not: mark it supported.
- Checked by: unit test.

**AC-006 Rounding down or hedging is fine, with a note**
- Given: draft says `over 38,000 customers`; sheet says `Customers: 38,412`.
- Then: `supported`, reason "Sheet says 38,412. 'Over 38,000' is a fair presentation."
- Checked by: unit test.

**AC-007 Years must match exactly**
- Given: draft says `founded in 2018`; sheet says `Founded: 2019`.
- Then: `contradicted`, fact F3.
- Must not: give years the 25 percent leeway.
- Checked by: unit test.

**AC-008 A number with nothing close on the sheet is unsupported**
- Given: draft says `900 employees`; the sheet has no employee figure.
- Then: `unsupported`, reason "No number on the sheet is within 25 percent of 900."
- Checked by: unit test.

**AC-009 On numbers, the code has the last word**
- Given: the model, for whatever reason, gives a different state to a span the code layer
  already judged.
- Then: the code's verdict stands and the model's is thrown away. `warnings` records
  "model verdict on '<span>' discarded (numeric)".
- Must not: let the model turn a `rounded_up` or `contradicted` number into anything better.
- Checked by: unit test with a fake model reply.

### The model layer (prose)

**AC-010 Prose is checked against the sheet and nothing else**
- Given: the sentence `Falcon Pay is headquartered in Dubai and led by CEO Layla Haddad.`
- Then: two claims, both `supported`, citing F6 and F4.
- Must not: send the draft anywhere but the configured model API. The prompt must contain
  nothing but the draft, the sheet, and the fixed instructions.
- Checked by: unit test with a fake model, plus a test that the prompt builder's output holds
  only those three things.

**AC-011 The model can only say "supported" by naming a real fact**
- Given: the fake model says `supported` citing `F9`, when only F1 to F6 exist.
- Then: the claim is dropped to `unsupported`, reason "Model cited F9 which does not exist",
  and `warnings` records it.
- Must not: show green for a citation that cannot be checked.
- Checked by: unit test.

**AC-012 A boast with no fact behind it is unsupported, not contradicted**
- Given: `the fastest-growing fintech in the Gulf`, and no growth fact on the sheet.
- Then: `unsupported`, with a reason that names what is missing ("No growth or ranking fact
  on the sheet").
- Checked by: eval case.

**AC-013 Things that are not claims are left alone**
- Given: `For more information, contact press@falconpay.com.`
- Then: no claim is made for that sentence.
- Checked by: eval case.

**AC-014 If the model fails, the check degrades. It never passes by accident.**
- Given: the model API times out (5 seconds) or sends back broken JSON.
- Then: the number results still show. `model_used` is false. `warnings` includes "Prose
  claims were not checked: <reason>". The page shows a clear banner. Approve is disabled no
  matter what the colours say.
- Must not: return an empty claims list with `approvable: true`.
- Checked by: unit test with a fake model that fails.

### The page

**AC-015 One click, and the highlights appear in the draft**
- Given: the sample draft and sample sheet are loaded; click Check.
- Then: within 5 seconds the draft shows all four highlight styles, the summary line reads
  "9 claims checked. 6 supported. 1 rounded up. 1 contradicted. 1 unsupported." (these
  counts are fixed by the shipped sample), and the draft text is otherwise untouched.
- Must not: reflow or change the draft text, or need any other setting.
- Checked by: by hand, in the demo video; plus a test that the API returns the sample's
  expected counts.

**AC-016 Hover explains in one sentence**
- Given: hover over any highlight.
- Then: a tooltip shows the `reason` text. No fact IDs, no JSON.
- Checked by: by hand.

**AC-017 Approve is gated**
- Given: there is any `contradicted` or `rounded_up` claim, or `model_used` is false.
- Then: Approve is disabled, and hovering it says why ("1 contradicted, 1 rounded up").
- Given: only `supported` and `unsupported` claims remain, and the model ran.
- Then: Approve is enabled. Clicking it shows "Approved" and nothing more (nothing is saved;
  see "What is out").
- Checked by: by hand, plus a unit test on the `approvable` rule.

**AC-018 Fix it, check again**
- Given: change `2018` to `2019` in the draft and click Check again.
- Then: the red highlight is gone, the summary updates, and Approve is still disabled, now
  only because of the orange one.
- Checked by: by hand, in the video.

### Sample content

**AC-019 The sample plants exactly one mistake per colour**
- Given: `samples/draft.txt` and `samples/facts.txt` as committed.
- Then: one `rounded_up` (`$13 million` against `$12.4 million`), one `contradicted` (`2018`
  against `2019`), one `unsupported` (the Gulf boast), and every other claim `supported`.
- Checked by: a test that asserts the exact summary counts.

### Tests, evals, and CI

**AC-020 Tests run with one command**
- Then: `pytest` passes locally and in CI on every push to main.
- Checked by: the CI status on the repo.

**AC-021 An eval set with a real, measured score**
- Given: `evals/cases/` holds at least 12 labelled cases (draft, sheet, expected claims and
  states), including AC-012 and AC-013.
- Then: `python -m evals` prints precision and recall per state for the model layer, and one
  number for the code layer. Those numbers go in the README exactly as measured, not
  rounded.
- Must not: let CI pass if the code layer's recall on the eval set is under 100 percent.
  Model layer scores are reported but do not block, in revision 1.
- Checked by: the CI job output.

**AC-022 Runs with one command from a fresh clone (Nice to have)**
- Then: `uv run vouch` (or `make run`) starts the server on localhost:8000 with the sample
  loaded, and the README says so in its first ten lines.
- Checked by: by hand, on a fresh clone.

## Dark features

- `CHECK_QUOTES` (off by default). When on, quoted sentences in the draft are matched against
  `Quote:` lines on the sheet. A quote that is not on the sheet is `unsupported`, reason
  "Quote not on the approved sheet". It ships unfinished: the parsing exists, the page shows
  nothing. It is there to show how the switch works and to leave an obvious next step.

## Stack

Python 3.12, FastAPI, DeepSeek's chat API through its OpenAI-compatible endpoint (model ID
read from the environment and set in one place), one HTML page with plain JavaScript served by
FastAPI, pytest, GitHub Actions. No database. No front-end framework.

DeepSeek over Claude on purpose. The model's job here is extraction against a short sheet, not
reasoning, and the two perform alike on that while DeepSeek costs a fraction per call. Nothing
in the design depends on which model sits behind the guards in AC-011 and AC-014, so swapping
later is a one-file change.

Next.js was skipped on purpose: it would double the amount of code for no gain in a two-evening
build.

## Other rules

- Nothing is saved anywhere. The draft only leaves the process as a call to the model API.
- The model call has a 5-second timeout and one retry. If it still fails, AC-014 applies.
- The code layer runs with the model switched off (`MODEL=off`) for tests and offline demos.

## Risks

- R1. Matching a number to the right fact is the weakest part. A number near a fact is not
  always that fact. Plan: match by value first, then by the nearest label word in the same
  sentence. Log the misses in the eval output rather than hiding them.
- R2. The model may call a claim supported when a human would call it a stretch. Plan:
  AC-011 forces it to cite a fact, and the eval set includes stretch cases.
- R3. The demo depends on the model API being up. Plan: `MODEL=off` still shows the number
  highlights, and the video records both modes.

## Open questions (answered by assumption for revision 1)

- Q1. Should `rounded_up` block Approve, or only warn? Assumed: block (A2).
- Q2. Should `unsupported` block Approve? Assumed: warn only (A3).

## Build order

1. Fact sheet parser (AC-001, AC-002).
2. Finding numbers and judging them (AC-003 to AC-009), tests, the `MODEL=off` path.
3. Sample content and the counts test (AC-019).
4. The page: highlights, summary, gated Approve (AC-015 to AC-018), on number results only.
5. The model layer, with the citation guard and the failure path (AC-010 to AC-014).
6. Eval set and script, CI (AC-020, AC-021).
7. The dark quote switch, README with measured scores, one-command run (AC-022).

Each step is one or more small commits straight to main. Nothing lands without its tests.
