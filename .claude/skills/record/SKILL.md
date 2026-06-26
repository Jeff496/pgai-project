---
name: record
description: Write a brief overview of what happened during the current session into a new file under session-logs/, flagging important notices and follow-ups (e.g. async webhook timing, unwired steps, decisions to revisit). Use when the user types /record or asks to "record", "log", or "note down" what happened this session.
---

# /record — session recap

Write a short, scannable recap of the **current session** to a **new file** under `session-logs/` at the repo root (create the directory if it doesn't exist). Each invocation is its own file — never append to or overwrite an existing log.

## Filename

`session-logs/<NNN>-<kebab-topic>.md` — a zero-padded sequential number plus a 2-4 word kebab-case topic, e.g. `session-logs/001-amd-removal-recording-webhook.md`.

Pick `NNN` by scanning `session-logs/` for the highest existing `NNN-` prefix and adding 1 (start at `001` if the directory is empty or missing). This keeps logs ordered and lets multiple land on the same day without collisions. Never reuse a number or clobber a prior log.

## What to write

Keep it **lean** (project rule): a few bullets, not an essay. Capture what a teammate — or future-me starting a fresh session — would need to pick up where this one left off.

```markdown
# <YYYY-MM-DD> — <short topic>

**What happened**
- <bullet per meaningful change or outcome — what, and why if not obvious>

**Files touched**
- `path/to/file.py` — <one-line what changed>

**⚠️ Notices & follow-ups**
- <gotchas, async/timing caveats, unwired steps, things left out on purpose, decisions to revisit>
```

## Rules

- **Brief.** Bullets, not paragraphs. Skip anything obvious from the diff or git history.
- **Always include the `⚠️ Notices & follow-ups` section** — this is the point of the skill. Surface things like:
  - Async/timing caveats (e.g. "recording webhook fires *after* the call ends, not during the call flow").
  - Steps that were intentionally left unwired and what would complete them (e.g. "`/recording-status` handler only logs — next step is to call `download_recording(call_sid)` and save to `calls/<scenario_id>__<call_sid>.mp3`").
  - Anything the user said they'd handle separately, or decisions to revisit.
  - If there are genuinely no open items, write `- None` rather than dropping the section.
- Pull the notices from what actually happened this session — re-read the conversation, don't invent.
- After writing, tell the user one line: the file path you created and how many notices you flagged.
