"""OpenAI-powered conversation engine for the voice bot."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from bot.conversation import ConversationState, STAGE_GATHERING, STAGE_CONFIRM, STAGE_COMPLETE
from bot.quote_processor import QuoteDetails, QuoteProcessor
from config import settings

logger = logging.getLogger(__name__)

_processor = QuoteProcessor()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a friendly and professional insurance sales assistant for ArtradePro, \
helping callers convert a verbal insurance quote into a binding contract over the phone.

Your goal is to collect the following information from the caller:
1. Full name
2. Coverage type (life, health, auto, or property)
3. Coverage amount in Rands (e.g. R500,000)
4. Policy term in years (e.g. 10 years)
5. Email address (optional)
6. Contact phone number (optional)

Guidelines:
- Be warm, concise, and professional.
- Ask for one piece of information at a time.
- Confirm what you heard before moving on.
- Once all required fields are collected, summarise the quote and ask for confirmation.
- Keep responses SHORT — remember this is a phone call.
- Do NOT generate lengthy paragraphs; keep each response under 3 sentences.

When you have gathered all required information, output a JSON block wrapped in
<quote> ... </quote> tags containing the extracted fields:
{
  "full_name": "",
  "email": "",
  "phone": "",
  "coverage_type": "",
  "coverage_amount": 0,
  "term_years": 0,
  "notes": ""
}
Only output this block once you are ready to confirm the quote.
"""


# ---------------------------------------------------------------------------
# LLM client helper
# ---------------------------------------------------------------------------


class LLMEngine:
    """Wraps the OpenAI client to drive the quote-gathering conversation."""

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)

    def get_response(self, state: ConversationState) -> str:
        """Call the LLM with the current conversation history and return the reply."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state.messages_for_llm()
        try:
            completion = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=300,
                temperature=0.4,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return "I'm sorry, I'm having a technical difficulty. Could you please repeat that?"

    def extract_quote(self, text: str) -> QuoteDetails | None:
        """Parse a <quote>…</quote> JSON block from the LLM's output."""
        match = re.search(r"<quote>(.*?)</quote>", text, re.DOTALL)
        if not match:
            return None
        try:
            raw = json.loads(match.group(1))
            return _processor.process(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse quote JSON: %s", exc)
            return None
