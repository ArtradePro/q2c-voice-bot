"""Twilio voice-call webhook handlers.

Processes incoming TwiML requests and generates TwiML responses that drive
the Quote-to-Contract conversation over a phone call.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Sequence

from twilio.twiml.voice_response import VoiceResponse, Gather

from bot.conversation import (
    manager,
    STAGE_GREETING,
    STAGE_GATHERING,
    STAGE_CONFIRM,
    STAGE_COMPLETE,
    STAGE_CANCELLED,
)
from bot.llm_engine import LLMEngine
from bot.contract_generator import ContractGenerator
from bot.quote_processor import QuoteProcessor
from config import settings

logger = logging.getLogger(__name__)

_llm = LLMEngine()
_contract_gen = ContractGenerator()
_processor = QuoteProcessor()

GATHER_TIMEOUT = settings.speech_timeout
BASE_URL = settings.app_base_url.rstrip("/")


def _say(response: VoiceResponse, text: str) -> None:
    """Append a <Say> verb with consistent voice settings."""
    response.say(text, voice="Polly.Joanna", language="en-ZA")


def _gather_speech(response: VoiceResponse, action: str, timeout: int = GATHER_TIMEOUT) -> Gather:
    """Append a <Gather> verb configured for speech input."""
    gather = Gather(
        input="speech",
        action=f"{BASE_URL}{action}",
        method="POST",
        speechTimeout=str(timeout),
        language="en-ZA",
    )
    response.append(gather)
    return gather


# ---------------------------------------------------------------------------
# Handler: incoming call
# ---------------------------------------------------------------------------


def handle_incoming_call(call_sid: str) -> str:
    """Return TwiML for the initial greeting."""
    state = manager.get_or_create(call_sid)
    state.stage = STAGE_GREETING

    greeting = (
        "Welcome to ArtradePro Quote to Contract service. "
        "I'm your virtual insurance assistant. "
        "I'll help you generate an insurance contract in just a few minutes. "
        "Let's get started — what is your full name?"
    )
    state.add_message("assistant", greeting)
    state.stage = STAGE_GATHERING

    response = VoiceResponse()
    gather = _gather_speech(response, "/voice/gather")
    gather.say(greeting, voice="Polly.Joanna", language="en-ZA")

    # Fallback if caller doesn't speak
    _say(response, "I didn't catch that. Let me try again.")
    response.redirect(f"{BASE_URL}/voice/incoming", method="POST")

    return str(response)


# ---------------------------------------------------------------------------
# Handler: gather (mid-conversation)
# ---------------------------------------------------------------------------


def handle_gather(call_sid: str, speech_result: str) -> str:
    """Process caller speech and return the next TwiML prompt."""
    state = manager.get_or_create(call_sid)

    # Add user's speech to history
    state.add_message("user", speech_result)

    # Get LLM response
    llm_reply = _llm.get_response(state)

    # Strip any <quote> block from the spoken text
    spoken_text = re.sub(r"<quote>.*?</quote>", "", llm_reply, flags=re.DOTALL).strip()

    # Check if LLM embedded a quote JSON
    extracted_quote = _llm.extract_quote(llm_reply)
    if extracted_quote and extracted_quote.is_complete():
        state.quote = extracted_quote
        state.stage = STAGE_CONFIRM
        state.add_message("assistant", spoken_text)

        return _confirm_quote(state, spoken_text)

    state.add_message("assistant", spoken_text)

    response = VoiceResponse()
    gather = _gather_speech(response, "/voice/gather")
    gather.say(spoken_text, voice="Polly.Joanna", language="en-ZA")

    # Fallback
    _say(response, "I'm sorry, I didn't hear you. Please try again.")
    response.redirect(f"{BASE_URL}/voice/gather", method="POST")

    return str(response)


def _confirm_quote(state, spoken_text: str) -> str:
    """Build a TwiML response that reads back the quote and asks for confirmation."""
    summary = _processor.summarise(state.quote)
    confirm_msg = (
        f"{spoken_text} "
        f"Here is your quote summary: {summary}. "
        "Do you confirm this quote? Please say yes to confirm or no to start over."
    )

    response = VoiceResponse()
    gather = _gather_speech(response, "/voice/confirm", timeout=5)
    gather.say(confirm_msg, voice="Polly.Joanna", language="en-ZA")

    _say(response, "I didn't hear a response. Returning to the beginning.")
    response.redirect(f"{BASE_URL}/voice/incoming", method="POST")

    return str(response)


# ---------------------------------------------------------------------------
# Handler: confirmation
# ---------------------------------------------------------------------------


def handle_confirm(call_sid: str, speech_result: str) -> str:
    """Handle yes/no confirmation from the caller."""
    state = manager.get_or_create(call_sid)
    answer = speech_result.lower()

    response = VoiceResponse()

    def _word_in(word: str, text: str) -> bool:
        return bool(re.search(rf"\b{re.escape(word)}\b", text))

    yes_words = ("yes", "confirm", "correct", "yeah", "yep")
    no_words = ("no", "nope", "cancel", "restart", "start over")

    if any(_word_in(w, answer) for w in yes_words):
        # Generate contract
        contract_ref = f"Q2C-{uuid.uuid4().hex[:8].upper()}"
        contract_text = _contract_gen.generate(state.quote, contract_ref)

        state.stage = STAGE_COMPLETE
        state.confirmed = True
        logger.info("Contract generated: %s\n%s", contract_ref, contract_text)

        farewell = (
            f"Excellent! Your contract has been generated with reference number {contract_ref}. "
            f"Your monthly premium will be R {state.quote.premium_monthly:,.2f}. "
            "A copy will be sent to your email address if provided. "
            "Thank you for choosing ArtradePro. Have a wonderful day!"
        )
        _say(response, farewell)
        response.hangup()

    elif any(_word_in(w, answer) for w in no_words):
        state.stage = STAGE_CANCELLED
        manager.delete(call_sid)

        _say(response, "No problem! Let's start over. I'll transfer you back to the beginning.")
        response.redirect(f"{BASE_URL}/voice/incoming", method="POST")

    else:
        # Unclear — ask again
        confirm_msg = (
            "I'm sorry, I didn't quite catch that. "
            "Please say yes to confirm your quote, or no to start over."
        )
        gather = _gather_speech(response, "/voice/confirm", timeout=5)
        gather.say(confirm_msg, voice="Polly.Joanna", language="en-ZA")

    return str(response)


# ---------------------------------------------------------------------------
# Handler: call status callback
# ---------------------------------------------------------------------------


def handle_status_callback(call_sid: str, call_status: str) -> None:
    """Clean up conversation state when a call ends."""
    if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
        manager.delete(call_sid)
        logger.info("Call %s ended with status: %s", call_sid, call_status)
