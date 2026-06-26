"""Transcribe a dual-channel call recording with Deepgram Nova-3.

Each Twilio dual-channel leg is a separate Deepgram channel, so channel ==
speaker — no diarization guesswork.  We request utterances and render a single
time-ordered, speaker-labeled transcript (the per-call .txt artifact), which is
independent of the live session's transcript logging.
"""
import logging
import os

import httpx

from config import DEEPGRAM_API_KEY

logger = logging.getLogger(__name__)

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

# Channel index -> speaker label.  Empirically, for our Twilio *outbound*
# dual-channel recordings, channel 0 carries the answering party (the agent
# under test) and channel 1 carries the leg we placed (our patient bot).
CHANNEL_LABELS = {0: "AGENT", 1: "PATIENT"}


def transcribe_recording(mp3_path: str) -> dict:
    """POST an mp3 to Deepgram's prerecorded API; return the raw JSON result."""
    if not DEEPGRAM_API_KEY:
        raise ValueError("Missing DEEPGRAM_API_KEY.")

    with open(mp3_path, "rb") as f:
        audio = f.read()

    logger.info(f"[TRANSCRIBE] Sending {mp3_path} ({len(audio)} bytes) to Deepgram nova-3")
    resp = httpx.post(
        DEEPGRAM_URL,
        params={
            "model": "nova-3",
            "multichannel": "true",
            "punctuate": "true",
            "utterances": "true",
            "smart_format": "true",
        },
        content=audio,
        headers={
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/mpeg",
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def format_transcript(result: dict) -> str:
    """Render Deepgram utterances as time-ordered, speaker-labeled lines.

    e.g.  [00:11] AGENT: Thanks for calling Pivot Point Orthopedics...
          [00:13] BOT: Yes, this is Jordan.
    """
    utterances = result.get("results", {}).get("utterances", [])
    lines = []
    for u in sorted(utterances, key=lambda x: x.get("start", 0.0)):
        text = (u.get("transcript") or "").strip()
        if not text:
            continue
        ch = u.get("channel", 0)
        speaker = CHANNEL_LABELS.get(ch, f"CH{ch}")
        mm, ss = divmod(int(u.get("start", 0.0)), 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {speaker}: {text}")
    return "\n".join(lines)


def transcribe_to_file(mp3_path: str, txt_path: str | None = None) -> str:
    """Transcribe an mp3 and write the labeled transcript beside it (.txt)."""
    transcript = format_transcript(transcribe_recording(mp3_path))
    if txt_path is None:
        txt_path = os.path.splitext(mp3_path)[0] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(transcript + "\n")
    logger.info(f"[TRANSCRIBE] Wrote transcript -> {txt_path}")
    return txt_path
