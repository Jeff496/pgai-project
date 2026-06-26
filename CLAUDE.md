# PGAI Voice Bot — Project Memory

Outbound voice bot that calls Pretty Good AI's test agent (**+1-805-439-8008**), role-plays a **patient**, records + transcribes both sides, and surfaces bugs in their agent. The voice layer works and is lucid; current work is the **persona library + test harness** on top.

Full task brief: see `HARNESS_SPEC.md` — point me at it when working on the harness.

## Stack (do not re-architect)
- Forked from `deepgram-devs/deepgram-voice-agent-outbound-telephony`.
- Voice: Deepgram Voice Agent API — Flux STT + Aura-2 TTS + a Deepgram-**managed** LLM (`gpt-4o-mini`). The LLM is managed, so **only `DEEPGRAM_API_KEY` is needed for AI** (no OpenAI/Anthropic key).
- Telephony: Twilio (outbound + call recording). Server: Starlette + uvicorn on port **8080**.
- Dev: run locally, exposed via an ngrok static domain. Python 3.12 + venv.

## Already done — do NOT redo
- Baseline call works end-to-end via the tunnel; conversation is lucid.
- **AMD neutralized** (it otherwise routes an AI answerer to voicemail): in `voice_agent/session.py`, `_is_voicemail()` returns `False` and the late-detection voicemail switch was removed from `signal_amd_result()`.
- Persona swap started in `voice_agent/agent_config.py`.
- **Twilio recording wired** in `telephony/call_manager.py` (`record=True, recording_channels="dual"`) plus a `download_recording(call_sid)` helper that fetches the dual-channel `.mp3`.

## Rules (always)
- **The caller must behave like a real, improvising patient** with sensible turn-taking and pacing — never a scripted benchmark runner. Put sophistication into scenario setup + transcript analysis, never into making the call mechanical.
- **Keep it lean.** No job queue, worker pool, web dashboard, or A/B framework for the bot's own prompts. Scenario list + runner + capture + judge script + curation is the whole system.
- **Don't touch the working voice / AMD / audio path.** Build on top of it.
- **One phone number** for all calls.

## Gotchas
- **No hot reload** — restart `python main.py` after ANY code or `.env` change.
- The persona is parametrized **per call** via a "lead context" dict passed through `make_call` and injected into `_build_system_prompt` / `_build_greeting`. Each scenario = a context payload; reuse this path rather than hardcoding.

## Repo map (relevant files)
- `main.py` — Starlette + uvicorn entry point
- `config.py` — env vars (`DEEPGRAM_API_KEY`, `SERVER_*`, `TWILIO_*`, `ENDPOINT_SECRET`, `LLM_*`, `VOICE_MODEL`)
- `make_call.py` — CLI to place a call: `python make_call.py --to "+1..." [--lead-name "..." | --lead-file lead.json]`; reads `SERVER_EXTERNAL_URL` + `ENDPOINT_SECRET` from `.env`
- `telephony/routes.py` — `POST /make-call`, `WS /twilio`, `POST /amd-result`
- `telephony/call_manager.py` — places the Twilio call (recording lives here)
- `voice_agent/session.py` — Twilio↔Deepgram bridge; AMD (neutralized); barge-in; logs `ASSISTANT:` transcript lines to console
- `voice_agent/agent_config.py` — system prompt + greeting + `FUNCTIONS` + model config (**the persona lives here**)
- `voice_agent/function_handlers.py` + `backend/lead_service.py` — function dispatch + in-memory mock backend (`update_lead` = structured-outcome hook)

## Run
- Tunnel: `ngrok http --url=<static-domain> 8080`, then set `SERVER_EXTERNAL_URL` in `.env`.
- Server: `python main.py`. Place a call: `python make_call.py --to "+18054398008"`.
