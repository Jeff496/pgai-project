# Bug Report — Pretty Good AI test agent (+1-805-439-8008)

Curated issues found by role-playing a patient against the agent and reviewing the
recordings + transcripts. Quality over quantity — only well-evidenced issues that a
human has confirmed are listed here. Each bug points at the call artifact that proves
it (`calls/<scenario_id>__<call_sid>.{mp3,txt}`) with a timestamp and quote.

Candidate issues from the automated judge pass live separately; this file is the
curated shortlist.

---

## Bug 1 — Agent fabricates an existing appointment for a brand-new patient

- **Severity:** High
- **Call:** `calls/lead_4e5937__CAd148847c96efb655c1acd339b14492c4.txt` at `00:48`
- **What happened:** The caller introduces themselves unambiguously as new and states their goal — `[00:12] PATIENT: "Yes. That's me. I'm a new patient, and I'd like to book a routine checkup appointment."` After taking the date of birth, the agent replies: `[00:48] AGENT: "It looks like you already have a new patient checkup appointment booked. If you'd like, I can help you reschedule or cancel that appointment."` No such appointment exists — this is a first-ever contact.
- **Why it's a problem:** The hallucination derails the entire call. Instead of booking the check-up the caller asked for, the conversation is hijacked into a phantom reschedule/cancel flow, and the caller never gets what they called for. A real patient would be confused or alarmed by a mystery appointment they never made.
- **What it should have done:** Proceed to collect new-patient details and offer genuine available slots. If it truly believed a record existed, it should have been able to back the claim with concrete details (see Bug 2) rather than inventing one.

---

## Bug 2 — Agent asserts an appointment exists, then says it has no access to it

- **Severity:** High
- **Call:** `calls/lead_4e5937__CAd148847c96efb655c1acd339b14492c4.txt` at `00:48` → `01:07`
- **What happened:** Having claimed an appointment exists and offered to reschedule/cancel it (`[00:48]`), the agent is asked the obvious follow-up — `[00:59] PATIENT: "Could you let me know when that appointment is scheduled for?"` — and responds: `[01:07] AGENT: "I don't have access to your exact appointment details, but the clinic staff can provide that information."`
- **Why it's a problem:** It is logically inconsistent to know an appointment exists (confidently enough to offer to cancel it) while having no access to any of its details. The caller is left stuck, and the contradiction erodes trust in everything the agent says.
- **What it should have done:** Either have access to the details of an appointment it claims exists, or not assert the appointment in the first place. Don't offer an action (reschedule/cancel) the agent can't actually support.

---

## Bug 3 — Promised transfer dead-ends into a goodbye

- **Severity:** High
- **Call:** `calls/lead_4e5937__CAd148847c96efb655c1acd339b14492c4.txt` at `01:37`–`01:46`
- **What happened:** The agent offers to connect the caller to a team member (`[01:12]`), the caller accepts (`[01:17] PATIENT: "Yes. That would be great. Thank you."`), and the agent says `[01:37] AGENT: "Connecting you to a representative." [01:39] "Please wait."` Instead of a transfer, the call dead-ends: `[01:42] AGENT: "You've reached the Pretty Good AI test line. Goodbye."` and hangs up.
- **Why it's a problem:** The promised escalation connects to no one. The caller is explicitly told help is coming, then dropped with their issue unresolved — the worst-case outcome for a hand-off, since it sets and then breaks an expectation.
- **What it should have done:** Actually transfer or queue the caller. If no live transfer is possible, say so honestly and offer a real alternative (callback, take a message) rather than simulating a handoff that goes nowhere.
- **Also seen in:** `calls/reschedule_ambiguous__CA679822e63f10abe84c135f9b4c932d76.txt` at `01:43`–`01:48` — identical `"Connecting you to a representative." → "You've reached the Pretty Good AI test line. Goodbye."` Reproduced across two different scenarios, so it's a reliable failure, not a fluke.

---

## Bug 4 — Agent loops endlessly asking the caller to spell a name it already has

- **Severity:** High
- **Call:** `calls/reschedule_ambiguous__CA679822e63f10abe84c135f9b4c932d76.txt` at `00:42`–`01:13`
- **What happened:** The caller spells their name clearly, and the agent gets stuck re-asking for the last name **five times** in ~30 seconds, never accepting the four-letter name "Bell" — even when spelled phonetically:
  - `[00:46] PATIENT: "Of course. It's Marcus, m a r c u s, Bell."`
  - `[00:51] AGENT: "Could you also spell your last name for me?"`
  - `[00:56] AGENT: "Please go ahead and spell your last name."`
  - `[01:00] AGENT: "Please spell out your last name letter by letter."`
  - `[01:04] PATIENT: "Sure. It's b as in boy, e as in elephant, l as in lion..."`
  - `[01:10] AGENT: "Thank you. Please continue spelling your last name."`
  - `[01:13] PATIENT: "I already spelled it out. B e l l."`
- **Why it's a problem:** The agent demonstrably **already has the name** — it says `[00:50] "Thanks, Marcus."` and `[01:20] "Thank you, Marcus Bell."` — yet keeps looping. It burns ~30 seconds, frustrates the caller, and blocks the actual task (the reschedule never happens). A real patient would likely hang up.
- **What it should have done:** Accept the last name after the first clear spelling and move on; never re-ask a question whose answer it has already captured and echoed back.

---

## Bug 5 — Agent presumes the caller is "Jordan" regardless of who is calling (candidate)

- **Severity:** Low — candidate, needs confirmation
- **Call:** `calls/reschedule_ambiguous__CA679822e63f10abe84c135f9b4c932d76.txt` at `00:10` (and the same opening in both earlier calls)
- **What happened:** The agent opens **every** call with `[00:10] AGENT: "Am I speaking with Jordan?"` In this call the caller is Marcus Bell (`[00:12] PATIENT: "No. This is Marcus Bell..."`), yet the agent still greets "Jordan." Across all three test calls — two role-played as "Jordan," one as "Marcus" — the greeting always names Jordan.
- **Why it's a problem (if real):** Presuming a specific caller identity — likely remembered from a prior call on the same number, or a hardcoded default — is misleading and a potential privacy concern (volunteering a name tied to the number to whoever calls).
- **How to confirm:** We place every call from one Twilio number, so this could be cross-call state keyed to that number rather than a true bug. Confirm by calling as a clearly first-time caller (ideally from a different number) and checking whether it still opens with "Jordan."

---

_Last updated from 3 calls (`CAf3b501…` lead_35ccdb, `CAd14884…` lead_4e5937, `CA679822…` reschedule_ambiguous). More to come as scenarios are run._
