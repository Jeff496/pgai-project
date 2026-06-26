# PGAI Voice Bot — Harness & Persona Library Build Spec

> Task brief for building the **persona library + test harness**. Environment, stack, current state, behavioral rules, gotchas, and the repo map live in **`CLAUDE.md`** (auto-loaded) — read it first. This file is the task.

## What good output looks like (grading)

Judged in this priority order:
1. **Lucid voice conversation** — the gate (already cleared).
2. **Quality of bugs found** — useful, well-described issues beat a long list of nitpicks.
3. **Working code that makes real calls.**
4. **Clear thinking** — architecture doc + Loom walkthrough.
5. **Evidence of iteration** — did we improve after early results.
6. **Readable code** — understandable, not perfect.

The harness exists to drive **coverage** (trigger the agent's failures across scenarios). The value is in the **analysis + curation** of what it surfaces, not in the machinery.

## Scenario space to cover

Schedule; reschedule; cancel; medication refill; questions about office hours / locations / insurance; edge cases — interruptions / barge-in, ambiguous requests or dates, out-of-scope asks, impatient or rambling caller. Be creative about finding the agent's limits. Target **~12–15 scenarios** → 10+ good calls plus diversity.

## Components to build

### 1. Scenario / persona library (data, not code)
Each scenario is a data entry (a JSON/YAML file or dataclasses). Schema:
```yaml
- id: schedule_routine
  persona: "Jordan Reyes, DOB 1989-03-12. New patient, calm, slightly chatty."
  goal: "Book a routine check-up next week, afternoon preferred."
  opening_line: "Hi, I'd like to schedule an appointment with a doctor."   # used as the agent greeting
  pressure: none          # none | ambiguous_date | interruption | out_of_scope | background_noise | impatient
  expected_behavior: "Offers weekday slots, doesn't book outside office hours, collects new-patient info."   # what a CORRECT agent should do — used by the judge pass
```

### 2. Persona injection (refactor `voice_agent/agent_config.py`)
Make `_build_system_prompt(context)` and `_build_greeting(context)` build the **patient** persona from a scenario's fields (`persona`, `goal`, `opening_line`), passed in via the existing lead-context path. Keep the `VOICE FORMATTING RULES` block. Trim `FUNCTIONS` to just `end_call`. The prompt should produce natural, improvising, goal-directed behavior — never checklist-running.

### 3. Runner
Iterate the scenario library; for each scenario, place a call with that scenario's context (via `make_call`'s path), sequentially with a gap between calls. Tag each call with its `scenario id`.

### 4. Per-call capture (aligned artifact set, keyed `<scenario_id>__<call_sid>`)
- **Recording:** dual-channel `.mp3` via `download_recording(call_sid)` → `calls/<scenario_id>__<call_sid>.mp3`
- **Transcript** (both sides, with timestamps + speaker labels) → `calls/<scenario_id>__<call_sid>.txt`. Pick one source:
  - *(a)* Capture Deepgram conversation events in `session.py` for **both** roles to a per-call file (gives live timestamps). The repo currently logs only `ASSISTANT:` — add the user side.
  - *(b)* Transcribe the dual-channel recording afterward, labeling speaker by channel (channel = speaker; Deepgram Nova-3 is a good fit). Simpler.
- **Outcome JSON:** repurpose the `update_lead` hook to emit a per-call record (scenario id, what happened, candidate issues, summary) → `calls/<scenario_id>__<call_sid>.outcome.json`
- Keep **call ↔ recording ↔ transcript ↔ outcome ↔ bug** aligned by filename.

### 5. Judge / analysis pass
A script reads each transcript plus its scenario's `expected_behavior` and asks an LLM to flag **candidate issues**, each with: call ref, timestamp/quote, what happened, why it's a problem, severity → a candidate-bugs file. Assistive only — the human curates the real ones.

### 6. Bug report
Curated markdown — the strongest, best-described issues (quality > quantity). Format:
```
Bug: <one-line description>
Severity: High | Medium | Low
Call: <transcript file> at <timestamp>
Details: What happened (with the quote), why it's a problem, what the agent should have done instead.
```

## Build order

1. Refactor `agent_config.py` for patient-persona injection from a scenario context; trim `FUNCTIONS` to `end_call`.
2. Define the scenario library data file with ~3 scenarios to start.
3. Build the runner (loop → place call with context → pace → tag by scenario id).
4. Wire per-call capture: transcript-to-file + outcome JSON (the recording helper already exists). Enforce the filename keying.
5. Run a few real calls; verify the full artifact set lands for each.
6. Expand the library to ~12–15 scenarios; run the full set.
7. Judge pass → candidate bugs; human curates → bug report.
8. *(Later)* README (single-command run) + architecture doc (1–2 paragraphs) + `.env.example`; record the two videos.

## Deliverables checklist

- [ ] Working Python voice bot (forked repo + harness)
- [ ] README — single-command run after setup
- [ ] Architecture doc (1–2 paragraphs)
- [ ] ≥10 calls, both sides, audio in **ogg/mp3** + transcripts (aim 12–15)
- [ ] Bug report (curated, well-described)
- [ ] Loom walkthrough (≤5 min)
- [ ] AI-debugging screen recording (≤5 min)
- [ ] `.env.example`, no committed secrets
- [ ] Single E.164 phone number used for all calls
