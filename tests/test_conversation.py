"""Tests for conversation state management."""

import pytest
from bot.conversation import ConversationManager, ConversationState, STAGE_GREETING, STAGE_GATHERING


class TestConversationManager:
    def setup_method(self):
        self.mgr = ConversationManager()

    def test_get_or_create_new(self):
        state = self.mgr.get_or_create("CA123")
        assert isinstance(state, ConversationState)
        assert state.call_sid == "CA123"

    def test_get_or_create_existing(self):
        state1 = self.mgr.get_or_create("CA456")
        state1.stage = STAGE_GATHERING
        state2 = self.mgr.get_or_create("CA456")
        assert state2.stage == STAGE_GATHERING
        assert state1 is state2

    def test_get_missing(self):
        assert self.mgr.get("nonexistent") is None

    def test_delete(self):
        self.mgr.get_or_create("CA789")
        self.mgr.delete("CA789")
        assert self.mgr.get("CA789") is None

    def test_delete_nonexistent_no_error(self):
        self.mgr.delete("does-not-exist")  # Should not raise

    def test_active_count(self):
        assert self.mgr.active_count() == 0
        self.mgr.get_or_create("CA001")
        self.mgr.get_or_create("CA002")
        assert self.mgr.active_count() == 2
        self.mgr.delete("CA001")
        assert self.mgr.active_count() == 1


class TestConversationState:
    def test_add_and_retrieve_messages(self):
        state = ConversationState(call_sid="CA999")
        state.add_message("user", "Hello")
        state.add_message("assistant", "Hi there!")
        msgs = state.messages_for_llm()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Hello"}
        assert msgs[1] == {"role": "assistant", "content": "Hi there!"}

    def test_initial_stage(self):
        state = ConversationState(call_sid="CA100")
        assert state.stage == STAGE_GREETING

    def test_confirmed_default_false(self):
        state = ConversationState(call_sid="CA200")
        assert state.confirmed is False
