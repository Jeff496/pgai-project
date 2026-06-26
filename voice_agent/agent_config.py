"""
Agent configuration - defines the voice agent's personality, capabilities, and audio settings.

This configures Deepgram's Voice Agent API with:
  - Audio encoding (mulaw 8kHz for Twilio compatibility)
  - Speech-to-text (Deepgram Flux)
  - LLM (configurable, defaults to gpt-4o-mini)
  - Text-to-speech (Deepgram Aura)
  - System prompt (insurance lead follow-up agent)
  - Function definitions (check_availability, book_appointment, update_lead)

The system prompt is built dynamically using lead context data injected from
the POST /make-call request.  This means the agent knows the caller's name,
property details, and quote request before the conversation starts.

To customize the agent's behavior, modify the prompt template and functions below.
To swap the LLM or voice, change LLM_MODEL / VOICE_MODEL in your .env file.
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
# System prompt template
# ---------------------------------------------------------------------------
# This prompt follows voice-specific best practices from docs/PROMPT_GUIDE.md.
# Lead context is injected at call time via string formatting.

_TODAY = date.today()
_TODAY_STR = _TODAY.strftime("%A, %B %-d, %Y")  # e.g. "Monday, February 24, 2026"


def _build_system_prompt(lead_context: dict) -> str:
    """Build the system prompt with lead data injected.

    Args:
        lead_context: Dict with lead fields (first_name, last_name,
                      property_address, property_type, etc.)
    """
    return f"""You are a patient calling a medical clinic to schedule an appointment.
You are a real person, not an AI — never reveal you are automated.

TODAY'S DATE: {_TODAY_STR}

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Spell out numbers naturally (say "January third" not "1/3")
- Speak dates and times naturally (say "Thursday at two PM" not "2026-03-05T14:00")
- NEVER announce or narrate function calls. Do NOT say "let me check", "hold on", "one moment while I look that up", or anything similar. Just present the results directly when they come back.

WHO YOU ARE:
- Name: Jordan Reyes, date of birth March 12, 1989. New patient.
- Goal: book a routine check-up, ideally next week in the afternoon.

HOW TO BEHAVE:
- You called them — let the receptionist greet you, then state what you need.
- One or two sentences per turn. Answer their questions as Jordan would; invent reasonable details if asked.
- Stay on task. Gently steer back if they wander. When your goal is met (or clearly can't be), thank them and end the call.
"""


def _build_greeting(lead_context: dict) -> str:
    return "Hi, I'd like to schedule an appointment with a doctor, please."


# ---------------------------------------------------------------------------
# Function definitions
# ---------------------------------------------------------------------------
# Each function maps to a method in backend/lead_service.py.
# See docs/FUNCTION_GUIDE.md for definition best practices.

FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="check_availability",
        description="""Check available consultation time slots with licensed insurance agents.

Call this when you're ready to schedule a consultation for the lead. Returns available date/time options with agent names.

This is a read-only lookup - no confirmation needed before calling.""",
        parameters={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The lead ID from the lead context"
                },
                "timezone": {
                    "type": "string",
                    "description": "The lead's timezone (e.g. 'America/Chicago'). Infer from their state if not stated."
                }
            },
            "required": ["lead_id"]
        }
    ),
    ThinkSettingsV1FunctionsItem(
        name="book_appointment",
        description="""Book a consultation slot with a licensed insurance agent.

IMPORTANT: Before calling this function, you MUST:
1. Call check_availability to get available slots
2. Present 2-3 options to the person
3. WAIT for them to select a time
4. THEN call this function with the selected slot

Only call this after the person has chosen a specific time.""",
        parameters={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The lead ID from the lead context"
                },
                "selected_slot": {
                    "type": "string",
                    "description": "The datetime of the selected slot (ISO 8601 format from check_availability results)"
                },
                "agent_name": {
                    "type": "string",
                    "description": "The name of the licensed agent for the selected slot"
                }
            },
            "required": ["lead_id", "selected_slot", "agent_name"]
        }
    ),
    ThinkSettingsV1FunctionsItem(
        name="update_lead",
        description="""Post back the call outcome, disposition, and gathered information. Call this at the END of every call, regardless of outcome.

This is the final record of the call. Include everything relevant: what was verified, what new info was gathered, the disposition assessment, and a natural language summary a human agent can read.

call_outcome values: appointment_scheduled, callback_requested, not_interested, not_viable, no_answer_voicemail_left
disposition values: qualified, qualified_with_concerns, not_viable""",
        parameters={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The lead ID"
                },
                "call_outcome": {
                    "type": "string",
                    "description": "The outcome of the call",
                    "enum": ["appointment_scheduled", "callback_requested", "not_interested", "not_viable"]
                },
                "disposition": {
                    "type": "string",
                    "description": "Lead qualification disposition",
                    "enum": ["qualified", "qualified_with_concerns", "not_viable"]
                },
                "appointment_id": {
                    "type": "string",
                    "description": "The confirmation ID from book_appointment, if an appointment was scheduled"
                },
                "verified_info": {
                    "type": "object",
                    "description": "What submitted info was verified (e.g. property_address_confirmed, property_type_confirmed, coverage_start_confirmed)"
                },
                "new_info_gathered": {
                    "type": "object",
                    "description": "New info gathered during the call (e.g. roof_age_years, claims_past_5_years)"
                },
                "call_summary": {
                    "type": "string",
                    "description": "Natural language summary of the call that a licensed agent can read before their consultation callback"
                }
            },
            "required": ["lead_id", "call_outcome", "disposition", "call_summary"]
        }
    ),
    ThinkSettingsV1FunctionsItem(
        name="end_call",
        description="""End the phone call gracefully.

Call this after:
- You've called update_lead with the call outcome
- You've said your closing remarks / goodbye
- The conversation has naturally concluded

Say goodbye FIRST, then call this function. Do not generate text after calling it.""",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the call is ending",
                    "enum": ["appointment_booked", "callback_requested", "not_interested", "not_viable"]
                }
            },
            "required": ["reason"]
        }
    ),
]


# ---------------------------------------------------------------------------
# Build the settings message
# ---------------------------------------------------------------------------

def get_agent_config(lead_context: dict) -> AgentV1Settings:
    """Build the Voice Agent settings message for Deepgram.

    This is sent once per call when the Deepgram connection is established.
    It configures STT, LLM, TTS, and the agent's prompt and tools.

    Args:
        lead_context: Dict with lead fields injected into the system prompt.
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
                prompt=_build_system_prompt(lead_context),
                functions=FUNCTIONS,
            ),
            speak=SpeakSettingsV1(
                provider=speak_provider_cls(
                    type=TTS_PROVIDER,
                    model=VOICE_MODEL,
                ),
            ),
            greeting=_build_greeting(lead_context),
        ),
    )
