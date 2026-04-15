"""Tests for voice handler logic."""

import pytest
from unittest.mock import patch, MagicMock

from bot.voice_handler import handle_incoming_call, handle_gather, handle_confirm, handle_status_callback
from bot.conversation import manager, STAGE_GATHERING, STAGE_CONFIRM, STAGE_COMPLETE, STAGE_CANCELLED
from bot.quote_processor import QuoteDetails


class TestHandleIncomingCall:
    def test_returns_twiml_string(self):
        twiml = handle_incoming_call("CA_INC_001")
        assert isinstance(twiml, str)
        assert "<?xml" in twiml or "<Response>" in twiml

    def test_sets_gathering_stage(self):
        handle_incoming_call("CA_INC_002")
        state = manager.get("CA_INC_002")
        assert state is not None
        assert state.stage == STAGE_GATHERING

    def test_contains_greeting_text(self):
        twiml = handle_incoming_call("CA_INC_003")
        assert "ArtradePro" in twiml

    def teardown_method(self):
        for sid in ("CA_INC_001", "CA_INC_002", "CA_INC_003"):
            manager.delete(sid)


class TestHandleGather:
    def setup_method(self):
        self.call_sid = "CA_GATHER_001"
        handle_incoming_call(self.call_sid)

    @patch("bot.voice_handler._llm")
    def test_gather_adds_user_message(self, mock_llm):
        mock_llm.get_response.return_value = "What is your name?"
        mock_llm.extract_quote.return_value = None
        handle_gather(self.call_sid, "Hello there")
        state = manager.get(self.call_sid)
        user_msgs = [m for m in state.history if m.role == "user"]
        assert any("Hello there" in m.content for m in user_msgs)

    @patch("bot.voice_handler._llm")
    def test_gather_returns_twiml(self, mock_llm):
        mock_llm.get_response.return_value = "Can I have your name?"
        mock_llm.extract_quote.return_value = None
        result = handle_gather(self.call_sid, "I want life insurance")
        assert "<Response>" in result

    @patch("bot.voice_handler._llm")
    def test_gather_transitions_to_confirm_when_quote_complete(self, mock_llm):
        complete_quote = QuoteDetails(
            full_name="Alice Test",
            coverage_type="life",
            coverage_amount=500_000,
            term_years=10,
            premium_monthly=1_000,
        )
        mock_llm.get_response.return_value = (
            "Let me confirm. <quote>{}</quote>".format(
                '{"full_name":"Alice","coverage_type":"life","coverage_amount":500000,"term_years":10}'
            )
        )
        mock_llm.extract_quote.return_value = complete_quote
        handle_gather(self.call_sid, "Yes all correct")
        state = manager.get(self.call_sid)
        assert state.stage == STAGE_CONFIRM

    def teardown_method(self):
        manager.delete(self.call_sid)


class TestHandleConfirm:
    def _setup_confirmed_state(self, call_sid: str):
        handle_incoming_call(call_sid)
        state = manager.get(call_sid)
        state.stage = STAGE_CONFIRM
        state.quote = QuoteDetails(
            full_name="Test User",
            coverage_type="life",
            coverage_amount=500_000,
            premium_monthly=1_000,
            term_years=10,
        )
        return state

    def test_yes_completes_call(self):
        self._setup_confirmed_state("CA_CONF_001")
        twiml = handle_confirm("CA_CONF_001", "yes")
        state = manager.get("CA_CONF_001")
        assert state.stage == STAGE_COMPLETE
        assert state.confirmed is True
        assert "<Hangup" in twiml or "<hangup" in twiml.lower() or "hangup" in twiml.lower()

    def test_yes_response_contains_contract_ref(self):
        self._setup_confirmed_state("CA_CONF_002")
        twiml = handle_confirm("CA_CONF_002", "yes")
        assert "Q2C-" in twiml

    def test_no_cancels_call(self):
        self._setup_confirmed_state("CA_CONF_003")
        handle_confirm("CA_CONF_003", "no")
        state = manager.get("CA_CONF_003")
        # State should be cleaned up after cancellation
        assert state is None

    def test_unclear_response_reprompts(self):
        self._setup_confirmed_state("CA_CONF_004")
        twiml = handle_confirm("CA_CONF_004", "hmm not sure")
        state = manager.get("CA_CONF_004")
        # Stage should NOT be complete
        assert state.stage != STAGE_COMPLETE
        assert "<Gather" in twiml

    def teardown_method(self):
        for sid in ("CA_CONF_001", "CA_CONF_002", "CA_CONF_003", "CA_CONF_004"):
            manager.delete(sid)


class TestHandleStatusCallback:
    def test_completed_deletes_state(self):
        handle_incoming_call("CA_STATUS_001")
        assert manager.get("CA_STATUS_001") is not None
        handle_status_callback("CA_STATUS_001", "completed")
        assert manager.get("CA_STATUS_001") is None

    def test_failed_deletes_state(self):
        handle_incoming_call("CA_STATUS_002")
        handle_status_callback("CA_STATUS_002", "failed")
        assert manager.get("CA_STATUS_002") is None

    def test_in_progress_does_not_delete(self):
        handle_incoming_call("CA_STATUS_003")
        handle_status_callback("CA_STATUS_003", "in-progress")
        assert manager.get("CA_STATUS_003") is not None

    def teardown_method(self):
        for sid in ("CA_STATUS_001", "CA_STATUS_002", "CA_STATUS_003"):
            manager.delete(sid)
