"""Tests for FastAPI voice webhook endpoints."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "OK"


class TestVoiceIncoming:
    def test_incoming_call_returns_xml(self):
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CA_TEST_001", "CallStatus": "ringing"},
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        body = response.text
        assert "<Response>" in body
        assert "ArtradePro" in body

    def test_incoming_call_contains_gather(self):
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CA_TEST_002", "CallStatus": "in-progress"},
        )
        assert "<Gather" in response.text


class TestVoiceGather:
    def test_gather_no_speech_returns_xml(self):
        """When no speech is detected, the bot should re-prompt."""
        response = client.post(
            "/voice/gather",
            data={"CallSid": "CA_TEST_003", "SpeechResult": "", "Confidence": ""},
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]

    @patch("main.handle_gather")
    def test_gather_with_speech_calls_handler(self, mock_handle):
        mock_handle.return_value = "<Response><Say>Hello</Say></Response>"
        response = client.post(
            "/voice/gather",
            data={
                "CallSid": "CA_TEST_004",
                "SpeechResult": "My name is John",
                "Confidence": "0.95",
            },
        )
        assert response.status_code == 200
        mock_handle.assert_called_once_with("CA_TEST_004", "My name is John")


class TestVoiceConfirm:
    @patch("main.handle_confirm")
    def test_confirm_endpoint(self, mock_handle):
        mock_handle.return_value = "<Response><Say>Thank you</Say></Response>"
        response = client.post(
            "/voice/confirm",
            data={"CallSid": "CA_TEST_005", "SpeechResult": "yes"},
        )
        assert response.status_code == 200
        mock_handle.assert_called_once_with("CA_TEST_005", "yes")


class TestVoiceStatus:
    @patch("main.handle_status_callback")
    def test_status_callback(self, mock_handle):
        response = client.post(
            "/voice/status",
            data={"CallSid": "CA_TEST_006", "CallStatus": "completed"},
        )
        assert response.status_code == 204
        mock_handle.assert_called_once_with("CA_TEST_006", "completed")
