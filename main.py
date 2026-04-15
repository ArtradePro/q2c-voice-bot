"""FastAPI application — Quote 2 Contract Voice Bot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import PlainTextResponse

from bot.voice_handler import (
    handle_incoming_call,
    handle_gather,
    handle_confirm,
    handle_status_callback,
)
from bot.conversation import manager
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Q2C Voice Bot starting on %s:%s", settings.app_host, settings.app_port)
    yield
    logger.info("Q2C Voice Bot shutting down. Active conversations: %d", manager.active_count())


app = FastAPI(
    title="Q2C Voice Bot",
    description="Quote 2 Contract Voice Bot — ArtradePro",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "OK"


# ---------------------------------------------------------------------------
# Twilio voice webhooks
# ---------------------------------------------------------------------------


@app.post("/voice/incoming")
async def voice_incoming(
    CallSid: str = Form(...),
    CallStatus: str = Form(default=""),
):
    """Twilio calls this endpoint when a new call arrives."""
    logger.info("Incoming call: CallSid=%s", CallSid)
    twiml = handle_incoming_call(CallSid)
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/gather")
async def voice_gather(
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default=""),
):
    """Twilio calls this endpoint after the caller speaks during <Gather>."""
    logger.info("Gather: CallSid=%s SpeechResult=%r Confidence=%s", CallSid, SpeechResult, Confidence)
    if not SpeechResult:
        # No speech detected — re-prompt
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say(
            "I'm sorry, I didn't catch that. Could you please repeat?",
            voice="Polly.Joanna",
            language="en-ZA",
        )
        response.redirect(f"{settings.app_base_url.rstrip('/')}/voice/gather", method="POST")
        return Response(content=str(response), media_type="application/xml")

    twiml = handle_gather(CallSid, SpeechResult)
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/confirm")
async def voice_confirm(
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
):
    """Twilio calls this endpoint after the caller responds to the confirmation prompt."""
    logger.info("Confirm: CallSid=%s SpeechResult=%r", CallSid, SpeechResult)
    twiml = handle_confirm(CallSid, SpeechResult or "")
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/status")
async def voice_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(default=""),
):
    """Twilio calls this endpoint when the call status changes."""
    handle_status_callback(CallSid, CallStatus)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
