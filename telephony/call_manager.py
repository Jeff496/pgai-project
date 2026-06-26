"""
Outbound call manager - initiates calls via the Twilio REST API.

This module wraps the Twilio API for placing outbound calls.  When a call
is placed, Twilio dials the recipient and streams audio back to the server
via WebSocket.

The call flow:
  1. Server calls Twilio REST API with inline TwiML
  2. TwiML tells Twilio to open a WebSocket back to our /twilio endpoint
  3. Twilio dials the recipient's phone number
  4. When they pick up (or voicemail answers), audio flows over WebSocket
  5. Twilio's AMD runs in the background and POSTs result to /amd-result

The server must be publicly accessible (via Fly.io, ngrok, etc.) because
Twilio needs to open a WebSocket connection back to us.
"""
import logging
import os

import httpx
from twilio.rest import Client

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    SERVER_EXTERNAL_URL,
)

logger = logging.getLogger(__name__)


def place_call(to: str) -> str:
    """Place an outbound call via Twilio.

    Args:
        to: The phone number to call (E.164 format, e.g. +15551234567)

    Returns:
        The Twilio call SID (e.g. "CA...")

    Raises:
        ValueError: If required Twilio configuration is missing
        Exception: If the Twilio API call fails
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        raise ValueError(
            "Missing Twilio configuration. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in your .env file."
        )

    if not SERVER_EXTERNAL_URL:
        raise ValueError(
            "Missing SERVER_EXTERNAL_URL. Twilio needs a public URL to "
            "stream audio back. Set it in your .env file or use the setup wizard."
        )

    # Strip protocol prefix - TwiML needs a bare hostname for wss://
    host = SERVER_EXTERNAL_URL.replace("https://", "").replace("http://", "").rstrip("/")

    # Twilio POSTs here once the call recording is finished and ready to fetch,
    # so we don't have to poll recordings.list after every call.
    recording_callback_url = f"{SERVER_EXTERNAL_URL.rstrip('/')}/recording-status"

    # Build inline TwiML that tells Twilio to stream audio to our WebSocket
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twilio" />
    </Connect>
</Response>"""

    logger.info(f"[CALL_MANAGER] Placing call to {to}")
    logger.info(f"[CALL_MANAGER] Audio stream -> wss://{host}/twilio")
    logger.info(f"[CALL_MANAGER] Recording callback -> {recording_callback_url}")

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    call = client.calls.create(
        to=to,
        from_=TWILIO_PHONE_NUMBER,
        twiml=twiml,
        record=True,
        recording_channels="dual",
        recording_status_callback=recording_callback_url,
        recording_status_callback_event=["completed"],
        recording_status_callback_method="POST",
    )

    logger.info(f"[CALL_MANAGER] Call initiated - SID: {call.sid}")
    return call.sid


def download_recording(call_sid: str, filename_stem: str | None = None, calls_dir: str = "calls") -> str | None:
    """Download a call's dual-channel recording mp3 from Twilio.

    Looks up the recording for `call_sid` via the Twilio REST API and writes it
    to calls/<stem>.mp3.  `filename_stem` defaults to the call_sid; the harness
    passes "<scenario_id>__<call_sid>" so the audio lines up with the call's
    other artifacts (log, transcript, outcome).

    The recording was created with recording_channels="dual", so the .mp3 is a
    2-channel file — one call leg per channel.

    Returns the saved path, or None if the call has no recording yet.
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
        raise ValueError("Missing Twilio credentials (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN).")

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    recordings = client.recordings.list(call_sid=call_sid, limit=1)
    if not recordings:
        logger.warning(f"[CALL_MANAGER] No recording found for call {call_sid}")
        return None

    recording = recordings[0]
    media_url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}"
        f"/Recordings/{recording.sid}.mp3"
    )

    stem = filename_stem or call_sid
    os.makedirs(calls_dir, exist_ok=True)
    out_path = os.path.join(calls_dir, f"{stem}.mp3")

    logger.info(f"[CALL_MANAGER] Downloading recording {recording.sid} ({recording.duration}s) -> {out_path}")
    with httpx.stream(
        "GET", media_url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        follow_redirects=True,
        timeout=60.0,
    ) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)

    logger.info(f"[CALL_MANAGER] Saved recording -> {out_path}")
    return out_path
