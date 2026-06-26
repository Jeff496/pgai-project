"""Per-call log capture.

Attaches a file handler to the root logger for the lifetime of one call,
filtered to just that call's lines, so each call's logs land in their own
file:

    calls/<scenario_id>__<call_sid>.log

This makes a single call reviewable in isolation instead of scrolling one
interleaved console stream — when a call misbehaves you open one file
instead of grepping the whole run.

All artifacts for a call share the same stem (see artifact_key), so the
log sits next to that call's recording / transcript / outcome JSON.
"""
import logging
import os

CALLS_DIR = "calls"

# Maps call_sid -> scenario_id so post-call consumers (e.g. the recording
# webhook, which fires after the session is gone) can still recover the
# scenario this call belonged to.
call_scenarios: dict[str, str] = {}


def scenario_id_from_context(lead_context: dict) -> str:
    """Best scenario id we can derive from a call's context.

    Prefers an explicit "scenario_id" (set once the scenario library lands);
    falls back to the lead id, then "unknown".  This keeps filenames stable
    and forward-compatible before scenarios exist.
    """
    return lead_context.get("scenario_id") or lead_context.get("lead_id") or "unknown"


def artifact_key(scenario_id: str, call_sid: str) -> str:
    """Shared filename stem for every artifact of one call."""
    return f"{scenario_id}__{call_sid}"


class _CallSidFilter(logging.Filter):
    """Pass only log records whose message mentions this call_sid.

    Every per-call log line already carries the sid (e.g. "[SESSION:CA...]"),
    so this cleanly separates concurrent calls without threading state through
    every logger.
    """

    def __init__(self, call_sid: str):
        super().__init__()
        self.call_sid = call_sid

    def filter(self, record: logging.LogRecord) -> bool:
        return self.call_sid in record.getMessage()


def start_call_log(call_sid: str, scenario_id: str) -> logging.Handler:
    """Begin capturing this call's logs to calls/<scenario_id>__<call_sid>.log.

    Returns the handler — pass it to stop_call_log() when the call ends.
    """
    os.makedirs(CALLS_DIR, exist_ok=True)
    path = os.path.join(CALLS_DIR, f"{artifact_key(scenario_id, call_sid)}.log")

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    ))
    handler.addFilter(_CallSidFilter(call_sid))

    logging.getLogger().addHandler(handler)
    return handler


def stop_call_log(handler: logging.Handler | None) -> None:
    """Detach and close a per-call log handler.  Safe to call with None."""
    if handler is None:
        return
    logging.getLogger().removeHandler(handler)
    handler.close()
