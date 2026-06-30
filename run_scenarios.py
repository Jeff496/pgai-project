#!/usr/bin/env python3
"""
run_scenarios.py — drive the scenario library against the agent under test.

For each scenario this places a call through the *running server's* /make-call
endpoint (so the server injects that scenario's persona into the live call),
waits for the call to finish, then downloads + transcribes the recording —
keeping everything aligned as calls/<scenario_id>__<call_sid>.{mp3,txt,log}.

Calls are placed SEQUENTIALLY with a gap between them (one phone number, lean
by design — no parallelism). Capture is inline per call (option "a"): the
runner waits for each recording to finalize before starting the next scenario,
so every call is self-contained when its turn ends.

Prerequisites:
  - The server is running (python main.py) and reachable at SERVER_EXTERNAL_URL
  - .env has SERVER_EXTERNAL_URL, ENDPOINT_SECRET, TWILIO_*, DEEPGRAM_API_KEY

Usage:
  python run_scenarios.py                          # all scenarios -> test line
  python run_scenarios.py --scenario schedule_routine
  python run_scenarios.py --gap 30                 # seconds between calls
  python run_scenarios.py --dry-run                # show the plan, place no calls
  python run_scenarios.py --no-capture             # place calls, skip download/transcribe
"""
import argparse
import logging
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

from config import (
    SERVER_EXTERNAL_URL,
    ENDPOINT_SECRET,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
)
from scenario_library import load_scenarios, get_scenario
from telephony.call_logging import artifact_key
from telephony.call_manager import download_recording
from voice_agent.transcribe import transcribe_to_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("runner")

DEFAULT_TARGET = "+18054398008"  # Pretty Good AI test agent
TERMINAL_STATUSES = {"completed", "busy", "no-answer", "failed", "canceled"}


def place_scenario_call(to: str, scenario: dict) -> str:
    """Place a call via the running server, sending the scenario as the lead."""
    url = f"{SERVER_EXTERNAL_URL.rstrip('/')}/make-call"
    headers = {"Content-Type": "application/json"}
    if ENDPOINT_SECRET:
        headers["Authorization"] = f"Bearer {ENDPOINT_SECRET}"
    resp = httpx.post(url, json={"to": to, "lead": scenario}, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.json()["call_sid"]


def wait_for_call_end(client, call_sid: str, timeout: int = 420, poll: int = 4) -> str:
    """Poll Twilio until the call reaches a terminal status (or we time out)."""
    deadline = time.time() + timeout
    status = "unknown"
    while time.time() < deadline:
        status = client.calls(call_sid).fetch().status
        if status in TERMINAL_STATUSES:
            return status
        time.sleep(poll)
    return status


def wait_for_recording(client, call_sid: str, timeout: int = 60, poll: int = 3):
    """Poll until the call's recording has finished processing."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        recs = client.recordings.list(call_sid=call_sid, limit=1)
        if recs and recs[0].status == "completed":
            return recs[0]
        time.sleep(poll)
    return None


def run():
    parser = argparse.ArgumentParser(description="Run the scenario library against the agent under test")
    parser.add_argument("--to", default=DEFAULT_TARGET, help=f"Number to call (default {DEFAULT_TARGET})")
    parser.add_argument("--gap", type=int, default=20, help="Seconds to wait between calls (default 20)")
    parser.add_argument("--scenario", default=None, help="Run only this scenario_id (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan; place no calls")
    parser.add_argument("--no-capture", action="store_true", help="Place calls but skip download/transcribe")
    args = parser.parse_args()

    scenarios = [get_scenario(args.scenario)] if args.scenario else load_scenarios()
    logger.info(
        f"{len(scenarios)} scenario(s); target={args.to} gap={args.gap}s "
        f"capture={'off' if args.no_capture else 'on'}"
    )

    if args.dry_run:
        for s in scenarios:
            logger.info(f"  would call: {s['scenario_id']:24} pressure={s.get('pressure', 'none')}")
        return

    if not SERVER_EXTERNAL_URL:
        logger.error("SERVER_EXTERNAL_URL not set — configure .env / the server first.")
        sys.exit(1)

    # Pre-flight: is the server reachable? (Avoids burning gaps on a dead server.)
    try:
        httpx.get(SERVER_EXTERNAL_URL, timeout=10.0)
    except Exception as e:
        logger.error(f"Server at {SERVER_EXTERNAL_URL} is not reachable ({e}). Is `python main.py` running?")
        sys.exit(1)

    from twilio.rest import Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    results = []
    for i, scenario in enumerate(scenarios):
        sid = scenario["scenario_id"]
        logger.info(f"[{i + 1}/{len(scenarios)}] {sid}: placing call to {args.to}")
        try:
            call_sid = place_scenario_call(args.to, scenario)
        except Exception as e:
            logger.error(f"[{sid}] failed to place call: {e}")
            results.append((sid, None, "place-failed"))
            continue

        logger.info(f"[{sid}] call_sid={call_sid}; waiting for the call to finish...")
        status = wait_for_call_end(client, call_sid)
        logger.info(f"[{sid}] call ended (status={status})")

        if args.no_capture:
            results.append((sid, call_sid, status))
        else:
            stem = artifact_key(sid, call_sid)
            rec = wait_for_recording(client, call_sid)
            if not rec:
                logger.warning(f"[{sid}] no completed recording (status={status})")
                results.append((sid, call_sid, f"{status}/no-recording"))
            else:
                try:
                    mp3 = download_recording(call_sid, filename_stem=stem)
                    txt = transcribe_to_file(mp3)
                    logger.info(f"[{sid}] captured -> {mp3} + {txt}")
                    results.append((sid, call_sid, f"{status}/captured"))
                except Exception as e:
                    logger.error(f"[{sid}] capture failed: {e}")
                    results.append((sid, call_sid, f"{status}/capture-failed"))

        if i < len(scenarios) - 1:
            logger.info(f"pausing {args.gap}s before the next call...")
            time.sleep(args.gap)

    logger.info("=== run summary ===")
    for sid, call_sid, outcome in results:
        logger.info(f"  {sid:24} {call_sid or '-':36} {outcome}")


if __name__ == "__main__":
    run()
