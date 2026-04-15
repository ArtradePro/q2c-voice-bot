"""In-memory conversation state management for concurrent voice calls."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from bot.quote_processor import QuoteDetails


# ---------------------------------------------------------------------------
# Conversation stage constants
# ---------------------------------------------------------------------------

STAGE_GREETING = "greeting"
STAGE_GATHERING = "gathering"
STAGE_CONFIRM = "confirm"
STAGE_COMPLETE = "complete"
STAGE_CANCELLED = "cancelled"

ALL_STAGES = (
    STAGE_GREETING,
    STAGE_GATHERING,
    STAGE_CONFIRM,
    STAGE_COMPLETE,
    STAGE_CANCELLED,
)


# ---------------------------------------------------------------------------
# Message / history
# ---------------------------------------------------------------------------


@dataclass
class Message:
    role: str   # "system" | "assistant" | "user"
    content: str


# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------


@dataclass
class ConversationState:
    call_sid: str
    stage: str = STAGE_GREETING
    history: list[Message] = field(default_factory=list)
    quote: QuoteDetails = field(default_factory=QuoteDetails)
    confirmed: bool = False

    def add_message(self, role: str, content: str) -> None:
        self.history.append(Message(role=role, content=content))

    def messages_for_llm(self) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.history]


# ---------------------------------------------------------------------------
# Manager (thread-safe singleton)
# ---------------------------------------------------------------------------


class ConversationManager:
    """Stores and retrieves ConversationState objects keyed by Twilio CallSid."""

    def __init__(self) -> None:
        self._store: dict[str, ConversationState] = {}
        self._lock = threading.Lock()

    def get_or_create(self, call_sid: str) -> ConversationState:
        with self._lock:
            if call_sid not in self._store:
                self._store[call_sid] = ConversationState(call_sid=call_sid)
            return self._store[call_sid]

    def get(self, call_sid: str) -> Optional[ConversationState]:
        with self._lock:
            return self._store.get(call_sid)

    def delete(self, call_sid: str) -> None:
        with self._lock:
            self._store.pop(call_sid, None)

    def active_count(self) -> int:
        with self._lock:
            return len(self._store)


# Module-level singleton used by the application
manager = ConversationManager()
