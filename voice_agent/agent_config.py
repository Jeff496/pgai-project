"""
Agent configuration - defines the voice agent's personality, capabilities, and audio settings.

This configures Deepgram's Voice Agent API with:
  - Audio encoding (mulaw 8kHz for Twilio compatibility)
  - Speech-to-text (Deepgram Flux)
  - LLM (configurable, defaults to gpt-4o-mini)
  - Text-to-speech (Deepgram Aura)
  - System prompt (a PATIENT calling a clinic — the persona under test)
  - Function definitions (just end_call)

This bot role-plays a *patient* calling another voice agent so we can probe
that agent for bugs.  The persona is built dynamically per call from a
scenario's fields (persona, goal, opening_line, pressure), injected via the
lead-context path from POST /make-call.  Each scenario is a context payload;
the runner reuses this path rather than hardcoding personas here.

To customize behavior, edit the prompt template and the pressure behaviors
below.  To swap the LLM or voice, change LLM_MODEL / VOICE_MODEL in your .env.
"""
from datetime import date

from config import VOICE_MODEL, LLM_MODEL, LLM_PROVIDER, TTS_PROVIDER
from deepgram.agent.v1 import (
    AgentV1Settings,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V2,
)
from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1provider import (
    ThinkSettingsV1Provider_OpenAi,
    ThinkSettingsV1Provider_Anthropic,
    ThinkSettingsV1Provider_Google,
)
from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem
from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram


# ---------------------------------------------------------------------------
# Provider class lookup
# ---------------------------------------------------------------------------
_THINK_PROVIDERS = {
    "open_ai": ThinkSettingsV1Provider_OpenAi,
    "anthropic": ThinkSettingsV1Provider_Anthropic,
    "google": ThinkSettingsV1Provider_Google,
}

_SPEAK_PROVIDERS = {
    "deepgram": SpeakSettingsV1Provider_Deepgram,
}


# ---------------------------------------------------------------------------
# Persona defaults
# ---------------------------------------------------------------------------
# Used when a call arrives without scenario fields (e.g. a bare make_call with
# no lead file).  They mirror the original hardcoded persona so default
# behavior is unchanged; scenarios override them per call.
DEFAULT_PERSONA = (
    "Jordan Reyes, date of birth March 12, 1989. A new patient — calm, "
    "polite, and a little chatty."
)
DEFAULT_GOAL = (
    "Book a routine check-up appointment, ideally sometime next week in the "
    "afternoon."
)
DEFAULT_OPENING_LINE = "Hi, I'd like to schedule an appointment with a doctor, please."


# ---------------------------------------------------------------------------
# Pressure behaviors
# ---------------------------------------------------------------------------
# A scenario's `pressure` field maps to one extra line of *natural* behavior,
# woven into the prompt so the caller stays a real improvising person — never a
# mechanical trigger.  "none" adds nothing.
_PRESSURE_BEHAVIORS = {
    "none": "",
    "ambiguous_date": (
        "- Be vague about timing at first — say things like \"sometime next "
        "week\" or \"maybe Thursday, or was it Friday?\" — and make them work "
        "to pin you down to an exact day and time."
    ),
    "interruption": (
        "- You're eager and sometimes start talking before they've quite "
        "finished, or jump in with a follow-up mid-sentence, the way real "
        "people do on the phone."
    ),
    "out_of_scope": (
        "- At some natural point, ask for something the front desk probably "
        "can't handle (a medical opinion, a billing dispute, prescription "
        "advice) and see how they deal with it before getting back on track."
    ),
    "impatient": (
        "- You're short on time and a little impatient. Push to get things "
        "done quickly, cut off long explanations, and show mild frustration "
        "if they're slow or repeat themselves."
    ),
    "background_noise": (
        "- You're calling from somewhere noisy and distracted. Now and then "
        "mishear something, ask them to repeat it, or trail off and come back."
    ),
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_TODAY = date.today()
_TODAY_STR = _TODAY.strftime("%A, %B %-d, %Y")  # e.g. "Monday, February 24, 2026"


def _build_system_prompt(context: dict) -> str:
    """Build the patient persona's system prompt from a scenario context.

    Args:
        context: Scenario fields — `persona` (who the caller is), `goal` (why
                 they're calling), and optional `pressure` (a twist). Missing
                 fields fall back to the module defaults.
    """
    persona = context.get("persona") or DEFAULT_PERSONA
    goal = context.get("goal") or DEFAULT_GOAL
    pressure = context.get("pressure") or "none"
    pressure_note = _PRESSURE_BEHAVIORS.get(pressure, "")

    behavior_lines = [
        "- You placed this call. Let them greet you first, then explain why "
        "you're calling in your own words.",
        "- Talk like a real person: improvise, react, and make up believable "
        "details (dates, names, symptoms, insurance) on the spot if asked. "
        "Never read a list or sound scripted.",
        "- Keep each turn short — usually one or two sentences, like natural "
        "phone speech.",
        "- Pursue your goal, but go with the flow. Answer their questions as "
        "your character would; if they wander off, gently steer back.",
        "- Don't be a robot or a pushover — it's fine to be chatty, hesitant, "
        "or particular, depending on who you are.",
        "- Only wrap up once your goal is clearly handled (or clearly can't "
        "be). Then thank them, say a natural goodbye, and end the call. Don't "
        "hang up early, and don't narrate that you're ending it.",
    ]
    if pressure_note:
        behavior_lines.append(pressure_note)

    behavior = "\n".join(behavior_lines)

    return f"""You are a real person calling a medical clinic's front desk. You are NOT an AI and must never reveal or hint that you are automated — if asked, you're just a person on the phone.

TODAY'S DATE: {_TODAY_STR}

WHO YOU ARE:
{persona}

WHY YOU'RE CALLING:
{goal}

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Spell out numbers naturally (say "January third" not "1/3")
- Speak dates and times naturally (say "Thursday at two PM" not "2026-03-05T14:00")
- NEVER announce or narrate function calls. Do NOT say "let me check", "hold on", "one moment while I look that up", or anything similar. Just present the results directly when they come back.

HOW TO BEHAVE:
{behavior}
"""


def _build_greeting(context: dict) -> str:
    """The caller's opening line, spoken first when the call connects."""
    return context.get("opening_line") or DEFAULT_OPENING_LINE


# ---------------------------------------------------------------------------
# Function definitions
# ---------------------------------------------------------------------------
# The caller is a patient, not a service agent, so it only needs to hang up.
# end_call is dispatched in voice_agent/session.py.

FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="end_call",
        description="""End the phone call gracefully once the conversation is genuinely over.

Call this only after BOTH:
- Your goal has been handled, or it's clear the clinic can't help with it, AND
- You've already said a natural goodbye.

Say your goodbye FIRST, then call this. Do not say anything after calling it. Do NOT call this just because there's a short pause — only when the conversation has actually run its course.""",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you're ending the call",
                    "enum": ["goal_met", "goal_unreachable", "other"],
                }
            },
            "required": ["reason"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Build the settings message
# ---------------------------------------------------------------------------

def get_agent_config(context: dict) -> AgentV1Settings:
    """Build the Voice Agent settings message for Deepgram.

    This is sent once per call when the Deepgram connection is established.
    It configures STT, LLM, TTS, and the agent's prompt and tools.

    Args:
        context: Scenario context injected into the persona prompt + greeting.
    """
    think_provider_cls = _THINK_PROVIDERS.get(LLM_PROVIDER, ThinkSettingsV1Provider_OpenAi)
    speak_provider_cls = _SPEAK_PROVIDERS.get(TTS_PROVIDER, SpeakSettingsV1Provider_Deepgram)

    return AgentV1Settings(
        type="Settings",
        audio=AgentV1SettingsAudio(
            input=AgentV1SettingsAudioInput(
                encoding="mulaw",
                sample_rate=8000,
            ),
            output=AgentV1SettingsAudioOutput(
                encoding="mulaw",
                sample_rate=8000,
                container="none",
            ),
        ),
        agent=AgentV1SettingsAgent(
            listen=AgentV1SettingsAgentListen(
                provider=AgentV1SettingsAgentListenProvider_V2(
                    version="v2",
                    type="deepgram",
                    model="flux-general-en",
                ),
            ),
            think=ThinkSettingsV1(
                provider=think_provider_cls(
                    type=LLM_PROVIDER,
                    model=LLM_MODEL,
                ),
                prompt=_build_system_prompt(context),
                functions=FUNCTIONS,
            ),
            speak=SpeakSettingsV1(
                provider=speak_provider_cls(
                    type=TTS_PROVIDER,
                    model=VOICE_MODEL,
                ),
            ),
            greeting=_build_greeting(context),
        ),
    )
