# 2026-06-25 — AMD removal, recording webhook, /record skill

**What happened**
- Removed the answering-machine-detection (AMD) wait so the agent connects to Deepgram immediately on answer (was costing ~20s of dead air; we call an AI agent, not a person, so there's nothing to detect).
- Enabled Twilio call recording (`record=True`, dual channel) on outbound calls.
- Added a recording-status webhook so Twilio notifies us the moment each recording is ready — no more polling `recordings.list` after every call.
- Created a project skill `/record` that writes a per-session recap into `session-logs/`.

**Files touched**
- `voice_agent/session.py` — `start()` no longer waits on `_amd_result` / branches to voicemail; it creates the Twilio audio loop and calls `_connect_deepgram()` immediately. Dead AMD/voicemail methods left in place, harmless.
- `telephony/call_manager.py` — dropped AMD params from `calls.create(...)`; added `record=True`, `recording_channels="dual"`, and `recording_status_callback` (event `completed`, POST) pointing at `/recording-status`.
- `telephony/routes.py` — new `recording_status` handler logging `CallSid` / `RecordingSid` / `RecordingUrl` / status / duration.
- `main.py` — registered `POST /recording-status` and imported the handler.
- `.claude/skills/record/SKILL.md` — new `/record` skill.

**⚠️ Notices & follow-ups**
- The recording webhook fires **after the call ends** (recording must finish processing) — it's asynchronous from the call flow. Use the `CallSid` in the payload to map it back to a scenario.
- The `/recording-status` handler currently **only logs**. Next step to complete the harness capture: call `download_recording(call_sid)` (or fetch `RecordingUrl + ".mp3"`) and save to `calls/<scenario_id>__<call_sid>.mp3`. Left unwired because it needs the scenario-id mapping.
- With the AMD wait gone, the agent greets immediately and may briefly **overlap the other party's greeting** — expected; user will tune separately.
- Dead AMD code (`signal_amd_result`, `_is_voicemail`, `_deliver_voicemail`, `_switch_to_voicemail`, the `/amd-result` route) is still present but unused. Fine for now; candidate for later cleanup.
- The `/record` skill is a project skill, so it only becomes an invocable `/record` after a session reload. This entry was written by performing its steps manually.
- `main.py`'s module docstring still lists only the original 3 endpoints — didn't update the comment. Minor.
