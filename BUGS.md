# Bug Report — Pretty Good AI test agent (+1-805-439-8008)

Curated issues found by role-playing patients against the agent across **18 calls / 13
scenarios**, then reviewing the dual-channel recordings + transcripts. Quality over
quantity — only well-evidenced, systemic issues are listed here. Each points at the call
artifact that proves it (`calls/<scenario_id>__<call_sid>.{mp3,txt}`) and the Twilio
**recording SID (`RE…`)** so it can be pulled up and confirmed, with a timestamp and an
exact quote.

A set of additional observations look like **test-line scaffolding / hardcoded
placeholders** rather than product defects (the same phantom record, a non-wired
transfer, demo language). Those are split out into a separate **"Noted"** section below so
they don't inflate the real bug count — but they're recorded in case any are unintended.

The raw, uncurated judge output (96 candidates) lives in `CANDIDATE_BUGS.md`.

> **Severity legend:** High = blocks the caller's task. Medium = degrades the interaction
> or misleads. Listed bugs were confirmed against the transcripts by a human.

---

## Confirmed behavioral bugs

### Bug 1 — Agent abandons the core task instead of completing it

- **Severity:** High
- **Reproduced in:** most transactional calls (schedule, reschedule, cancel, refill).
- **Call:** `calls/cancel_appointment__CAb9c55b41cd53922c2e301a4cd383dc38.txt` — recording `REb34b9b23dc9c2bcaf6bae071caf9fee5` — at `01:34`
- **What happened:** Across booking, rescheduling, and cancelling, the agent collects identity info and then bails without ever attempting the action: `[01:34] AGENT: "I can't cancel the appointment right now, but I'll connect you to our patient support team for help."` It never locates the appointment, never offers slots, never books or cancels. The reschedule scenarios show the same shape — it never clarifies the ambiguous "Thursday or Friday" timing and never offers an alternative slot.
- **Why it's a problem:** Scheduling, rescheduling, and cancelling are the agent's core jobs, and it completed **none** of them in any call. The data collection it does perform is wasted because it never acts on it.
- **What it should have done:** Use the identity it collected to locate the appointment, then actually perform (or clearly progress) the booking/reschedule/cancellation and confirm it.
- **Also in:** `reschedule_ambiguous` (all three, `RE70e4d4f9…`, `REbefae288…`, `RE0f4e68df…`), `schedule_impatient` (`RE8d2f98a8…`), `schedule_interruption` (`REc1df12ff…`), `rambling_new_patient` (`REa6c6058e…`).

### Bug 2 — Agent loops endlessly asking the caller to spell a name it already has

- **Severity:** High
- **Call:** `calls/reschedule_ambiguous__CA679822e63f10abe84c135f9b4c932d76.txt` — recording `REbefae2885c284637f2d14d9352e685d8` — at `00:42`–`01:13`
- **What happened:** The caller spells a four-letter last name, and the agent re-asks for it **five times** in ~30 seconds, never accepting "Bell" even spelled phonetically:
  - `[00:46] PATIENT: "It's Marcus, m a r c u s, Bell."`
  - `[00:51] AGENT: "Could you also spell your last name for me?"`
  - `[00:56] AGENT: "Please go ahead and spell your last name."`
  - `[01:00] AGENT: "Please spell out your last name letter by letter."`
  - `[01:04] PATIENT: "It's b as in boy, e as in elephant, l as in lion..."`
  - `[01:10] AGENT: "Thank you. Please continue spelling your last name."`
  - `[01:13] PATIENT: "I already spelled it out. B e l l."`
- **Why it's a problem:** The agent demonstrably already has the name — it says `[00:50] "Thanks, Marcus."` and later `"Thank you, Marcus Bell."` — yet keeps looping, burning ~30s and blocking the task.
- **What it should have done:** Accept the name after the first clear spelling and move on; never re-ask a question whose answer it already captured and echoed back.
- **Also in:** `clinic_location` — recording `RE66badef9077c02303a2db5244e5f6d33` — where it repeatedly demands the caller spell her name (talking over her) for a simple address question.

### Bug 3 — Agent ignores urgency on a same-day emergency

- **Severity:** High
- **Call:** `calls/urgent_same_day__CA295d6bc6e0a494e95c7ba64f5f5c8b2a.txt` — recording `RE5adfef15e36e2af2c21e6d6831a8f9f5` — at `00:23`–`00:29`
- **What happened:** The caller says she hurt her knee badly and needs to be seen today, and states twice she's in significant pain. The agent never acknowledges it — it responds with routine data collection (`[00:29] AGENT: "Please provide your date of birth."`), never triages, never checks same-day availability, and never mentions urgent care.
- **Why it's a problem:** For an urgent, potentially time-sensitive medical situation, the agent showed no recognition of urgency and no escalation — it treated a same-day emergency identically to a routine booking.
- **What it should have done:** Acknowledge the pain, recognize the urgency, and either surface same-day options, route to a triage nurse, or honestly direct the caller to urgent care/ER — without false reassurance.

### Bug 4 — Agent doesn't recognize an out-of-scope prescription refill

- **Severity:** High
- **Reproduced in:** 2 of 2 refill calls.
- **Call:** `calls/refill_out_of_scope__CA0e7b82af2d3c8e9a973db619b4b8c364.txt` — recording `REf270f6a231323483c427f05443819aaa` — at `00:20`
- **What happened:** The caller clearly asks for a medication refill — `[00:20] PATIENT: "I need a refill on my post-op pain medication after knee surgery."` The agent never acknowledges the request or notes that refills aren't something a scheduling line handles. It launches straight into identity verification, fails to verify, and ends the call. The refill is never addressed at all.
- **Why it's a problem:** The agent neither handles the request nor honestly declines it — it silently treats an out-of-scope clinical request as if it were processing it, leaving a real medication need unmet.
- **What it should have done:** Recognize refills are out of scope, say so, and route to the nurse line / pharmacy / provider or take a message.
- **Also in:** `refill_out_of_scope__CAf35340e1ee1af657fb8c612be132489f` — recording `RE98d504ac0fe601004f2592b93861361c` — same failure.

### Bug 5 — Agent forces identity verification onto simple informational questions

- **Severity:** Medium
- **Call:** `calls/clinic_location__CA38c3c67aed9cdf86ac15ec9d21c625e5.txt` — recording `RE66badef9077c02303a2db5244e5f6d33` — at `00:17`
- **What happened:** For a public-info question (the clinic's address and parking), the agent demands full identity verification — `[00:17] AGENT: "Please provide the full name and date of birth of the patient you're calling about."` — then descends into the spelling loop (Bug 2) before eventually answering. The same friction appears in `insurance_question` (recording `RE77cfc4a08c5a9b57911ce2773c3fcedb`), where it asks for date of birth and says `"I need to confirm your record before I can answer that"` before a general "do you take Blue Cross?" question. By contrast, `office_hours_question` was answered directly — so the behavior is inconsistent.
- **Why it's a problem:** Address, parking, hours, and insurance-acceptance are general information that needs no PII. Gating them behind verification adds pointless friction.
- **What it should have done:** Answer general informational questions directly, reserving identity verification for account-specific actions.
- **Lower-confidence note:** the address it eventually gave (`"1234 Recovery Way"`, `"free fusion parking"`) looks possibly fabricated — worth checking against the real clinic details.

---

## Potential issue — confirm whether intended

### Bug 6 — New patients are told they already have an appointment

- **Severity:** High *if not intentional test-record behavior*
- **Call:** `calls/schedule_routine__CAd8f4dfab43e9a5462d690bfba956ac68.txt` — recording `RE267aa2007f2f237a8d63c14b1948616a` — at `01:20`
- **What happened:** A caller who clearly introduces themselves as a new patient is told `[01:20] AGENT: "It looks like you already have a new patient consultation booked. If you'd like, I can help you reschedule or cancel that appointment."` Same in `lead_4e5937` (recording `REa2046a03c56c9fd30f9b7951e23d2028`) at `00:48`, where the agent then **contradicts itself** when asked for details: `[01:07] AGENT: "I don't have access to your exact appointment details, but the clinic staff can provide that information."`
- **Caveat (why this is "potential"):** This is most likely the **hardcoded phantom record** (see Noted N2/N3) surfacing its "appointment." If that record is intentional test scaffolding, the false claim is expected here. **But** two things are worth confirming regardless: (a) whether a real new patient in production could be told they have a nonexistent appointment, and (b) the **self-contradiction** — claiming an appointment exists while having no access to any detail of it — which is a genuine logic flaw independent of the hardcoded data.
- **What it should do (if real):** Treat a new patient as new; never claim a record it can't actually produce.

---

## Noted — likely test-line scaffolding (not counted as product bugs)

These reproduced strongly but read as hardcoded placeholders or un-wired test-environment behavior, not defects in the production agent. Recorded here in case any are unintended.

- **N1 — Every escalation dead-ends at a "test line" (14 of 18 calls).** Escalations end with `AGENT: "Hello. You've reached the Pretty Good AI test line. Goodbye."` and hang up — e.g. `urgent_same_day` (`RE5adfef15…`) at `02:11`. **Likely a real warm-transfer to a human that simply isn't wired on this test number.** Flag only if escalations are expected to connect in this environment. *(Note: this masks the true outcome of several calls — the agent's "I'll connect you" is its universal fallback, so we can't see what a working handoff would do.)*
- **N2 — Same phantom phone number `(971) 459-3958` read back to 10 different callers.** During "verification" the agent asserts this identical number to people who never gave it — e.g. `rambling_new_patient` (`REa6c6058e…`) at `02:05`, where the caller had just said he wasn't sure they had his number. **Likely a hardcoded placeholder record.** Worth noting in case it's a real number (privacy) or leaks into production.
- **N3 — Greets every caller as "Jordan" (18 of 18 calls).** Every call opens `AGENT: "Am I speaking with Jordan?"` regardless of who's calling — e.g. `schedule_interruption` (`REc1df12ff…`) at `00:10`. Same hardcoded test record as N2.
- **N4 — Leaks "for demo purposes" to the caller.** `schedule_routine` (`RE267aa200…`) at `00:30`: `AGENT: "The birthday doesn't match our records, but for demo purposes, I'll accept it."` Demo scaffolding surfacing in the conversation — a non-issue for production, but the "doesn't match our records" phrasing for a brand-new patient is worth a glance (ties to Bug 6).

---

## What the agent got right (for balance)

The agent isn't uniformly broken, which makes the failures above stand out as inconsistencies:

- **`office_hours_question`** (recording `RE4026b7ec396afdd8c29252cb63a75dec`) — answered the hours question directly and accurately, including the Saturday follow-up, without forcing verification.
- **`specific_provider_new_patient`** (recording `REb2bff4c0f0f2052cce41e984d9d5c797`) — correctly said Dr. Patel isn't a provider at the clinic, **did not fabricate** a schedule or booking, and offered legitimate alternatives — the honest behavior missing elsewhere.

---

_Generated from 18 calls across 13 scenarios. Drawn from `CANDIDATE_BUGS.md` (judge pass) and confirmed against the dual-channel transcripts + recordings in `calls/`._
