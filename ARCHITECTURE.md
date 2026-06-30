# Architecture

This project is a **patient-roleplay test harness** built on a forked Deepgram + Twilio
outbound voice-agent stack. The voice core is unchanged in spirit: the server places an
outbound call via Twilio, bridges the call's audio over a WebSocket to Deepgram's Voice
Agent API (Flux STT → a Deepgram-managed `gpt-4o-mini` → Aura-2 TTS) inside a single
`VoiceAgentSession`, with barge-in and dual-channel recording. What changed is the
**role**: instead of an insurance receptionist, the agent is prompted *per call* to behave
as a **patient calling a clinic**, so we can dial Pretty Good AI's test line, hold a real
improvising conversation, and surface bugs in *their* agent. The persona rides the existing
lead-context path — each scenario's `persona`, `goal`, `opening_line`, and `pressure` fields
flow from `POST /make-call` into `_build_system_prompt` / `_build_greeting` in
`voice_agent/agent_config.py` (the only voice-path change of note beyond removing the
answering-machine wait, since the callee is another bot, not a person).

On top of that voice core sits a five-stage pipeline, deliberately lean (no job queue, no
dashboard) — the machinery only exists to drive coverage; the value is in the analysis:

```
scenarios/*.json ─▶ run_scenarios.py ─▶ [place call → server injects persona] ─▶
   download_recording + transcribe ─▶ calls/<scenario_id>__<call_sid>.{mp3,txt,log} ─▶
   judge.py (Claude) ─▶ CANDIDATE_BUGS.md ─▶ human curation ─▶ BUGS.md
```

1. **Scenario library** — `scenarios/*.json`, one patient persona per file; loaded and
   validated by `scenario_library.py`.
2. **Runner** — `run_scenarios.py` iterates the library and places each call sequentially
   through the running server, waiting for each to finish (one phone number, no parallelism).
3. **Capture** — per call, it downloads the Twilio dual-channel recording
   (`download_recording` in `telephony/call_manager.py`) and transcribes it per-channel with
   Deepgram Nova-3 (`voice_agent/transcribe.py`), writing artifacts keyed
   `calls/<scenario_id>__<call_sid>.*` so audio ↔ transcript ↔ log stay aligned.
4. **Judge** — `judge.py` sends each transcript plus its scenario's `expected_behavior` to
   Claude (`claude-opus-4-8`, structured output) to flag candidate issues into
   `CANDIDATE_BUGS.md`. Coverage-first and assistive.
5. **Curation** — a human distills the candidates into the committed `BUGS.md`, filtering
   transcription noise and test-line scaffolding from genuine agent defects.

For a deeper look at the voice/audio layer specifically (session lifecycle, the WebSocket
bridge, barge-in), see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — note it predates the
patient-persona refactor and still describes the original insurance receptionist.
