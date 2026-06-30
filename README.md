# PGAI Voice Bot — Patient-Roleplay Test Harness

An outbound voice harness that **calls Pretty Good AI's test agent** (`+1‑805‑439‑8008`),
role-plays a **patient** calling a medical clinic, records and transcribes both sides of the
conversation, and uses an LLM judge + human curation to surface **bugs in their agent**.

It's built on a forked Deepgram + Twilio outbound voice-agent stack (Flux STT → a
Deepgram-managed `gpt-4o-mini` → Aura-2 TTS, bridged to Twilio over a WebSocket). The novel
part is everything on top: a scenario/persona library, a runner, per-call capture, an
LLM judge, and a curated bug report.

- **Results:** see **[`BUGS.md`](BUGS.md)** — the curated findings.
- **How it fits together:** see **[`ARCHITECTURE.md`](ARCHITECTURE.md)** (1‑2 paragraphs).

---

## How it works

```
scenarios/*.json ─▶ run_scenarios.py ─▶ place call (server injects persona) ─▶
   download recording + transcribe ─▶ calls/<scenario_id>__<call_sid>.{mp3,txt,log} ─▶
   judge.py (Claude) ─▶ CANDIDATE_BUGS.md ─▶ human curation ─▶ BUGS.md
```

Each scenario is a data file describing a patient (`persona`, `goal`, `opening_line`,
`pressure`, `expected_behavior`). The runner places one call per scenario, the persona is
injected into the live call, and each call is captured as aligned artifacts. The judge reads
each transcript against its scenario's `expected_behavior` and flags candidate issues; a
human curates the real ones into `BUGS.md`.

---

## Setup

### Prerequisites

- Python 3.12+
- A [Deepgram](https://console.deepgram.com/) API key (in-call LLM + transcription)
- A [Twilio](https://www.twilio.com/try-twilio) account with a phone number (outbound calls + recording)
- A tunnel to expose the local server (e.g. [ngrok](https://ngrok.com/)) — Twilio opens a WebSocket back to it
- An [Anthropic](https://console.anthropic.com) API key — **only** for the judge pass (`judge.py`)

### 1. Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Fill in:

```
DEEPGRAM_API_KEY=...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
SERVER_EXTERNAL_URL=https://<your-tunnel>.ngrok-free.dev
ENDPOINT_SECRET=...            # any secret; authenticates POST /make-call
ANTHROPIC_API_KEY=...          # only needed to run judge.py
```

> **No hot reload** — restart `python main.py` after any code or `.env` change.

### 3. Start the tunnel + server

```bash
ngrok http 8080            # copy the https URL into SERVER_EXTERNAL_URL in .env
python main.py             # in a second shell
```

---

## Run it

### The whole set (single command)

With the server + tunnel up:

```bash
python run_scenarios.py
```

This places a call for **every** scenario in `scenarios/`, sequentially with a gap, and for
each one downloads the recording and writes the transcript — leaving aligned artifacts in
`calls/`. Useful flags:

```bash
python run_scenarios.py --dry-run                 # show the plan, place no calls
python run_scenarios.py --scenario schedule_routine   # just one
python run_scenarios.py --gap 30                  # seconds between calls
```

### One scenario by hand

Scenario files double as `make_call.py --lead-file` inputs:

```bash
python make_call.py --to "+18054398008" --lead-file scenarios/reschedule_ambiguous.json
```

### Judge the transcripts

```bash
python judge.py --all        # writes CANDIDATE_BUGS.md (assistive, uncurated)
```

Then a human promotes the genuine ones into `BUGS.md`.

---

## Artifacts

Everything for a call shares the key `<scenario_id>__<call_sid>`:

```
calls/
  schedule_routine__CA1234….mp3              # dual-channel recording (gitignored)
  schedule_routine__CA1234….txt              # per-channel transcript (AGENT / PATIENT, timestamps)
  schedule_routine__CA1234….log              # this call's server logs, in isolation
  schedule_routine__CA1234….candidates.json  # judge output for this call
```

`calls/` and `CANDIDATE_BUGS.md` are gitignored (run artifacts); `BUGS.md` is the committed
deliverable.

---

## Adding a scenario

Drop a JSON file in `scenarios/`:

```json
{
  "scenario_id": "cancel_appointment",
  "persona": "Priya Nair, date of birth April 22, 1980. Existing patient, organized and polite.",
  "goal": "Cancel an upcoming physical-therapy follow-up appointment.",
  "opening_line": "Hi, I need to cancel an appointment I have scheduled.",
  "pressure": "none",
  "expected_behavior": "Verifies identity, locates the appointment, and cancels it — without inventing details or dead-ending the caller."
}
```

`pressure` ∈ `none | ambiguous_date | interruption | out_of_scope | background_noise | impatient`
— it's woven into the persona prompt as natural behavior. `expected_behavior` is what the
judge grades against.

---

## Repo map (harness)

| Path | Role |
|---|---|
| `scenarios/*.json` | Scenario/persona library (data) |
| `scenario_library.py` | Loads + validates scenarios |
| `run_scenarios.py` | Runner: loop → call → capture → transcribe |
| `judge.py` | LLM judge pass → `CANDIDATE_BUGS.md` |
| `BUGS.md` | Curated bug report (the deliverable) |
| `voice_agent/agent_config.py` | Patient-persona injection (`_build_system_prompt` / `_build_greeting`) |
| `voice_agent/transcribe.py` | Dual-channel transcription (Deepgram Nova-3) |
| `telephony/call_manager.py` | Places calls; `download_recording()` |
| `telephony/routes.py` | `POST /make-call`, `WS /twilio`, `/recording-status` |
| `voice_agent/session.py` | Twilio ↔ Deepgram audio bridge |

The underlying voice infrastructure (forked from
[deepgram-voice-agent-outbound-telephony](https://github.com/deepgram-devs/deepgram-voice-agent-outbound-telephony))
is documented in `docs/` — note those docs predate the patient-persona refactor.
