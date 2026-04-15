# q2c-voice-bot
Quote 2 Contract Voice Bot

A phone-based AI voice bot for ArtradePro that guides callers through an insurance
quote and automatically generates a binding contract — all over a standard phone call.

---

## Overview

The **Q2C Voice Bot** uses:

- **[Twilio](https://twilio.com)** – inbound phone call handling and TwiML voice responses
- **[OpenAI GPT](https://platform.openai.com)** – conversational intelligence for gathering quote details
- **[FastAPI](https://fastapi.tiangolo.com)** – lightweight async web framework for Twilio webhooks

### Call flow

```
Caller dials Twilio number
        │
        ▼
[/voice/incoming]  — greeting & first prompt
        │
        ▼
[/voice/gather]    — repeated conversational turns (speech → LLM → TwiML)
        │
        ▼
[/voice/confirm]   — quote summary read back, yes/no confirmation
        │
        ▼
Contract reference issued & call ended
```

Gathered information:

| Field            | Required |
|------------------|----------|
| Full name        | ✅       |
| Coverage type    | ✅       |
| Coverage amount  | ✅       |
| Policy term      | ✅       |
| Email address    | Optional |
| Contact number   | Optional |

---

## Getting started

### Prerequisites

- Python 3.11+
- A [Twilio](https://console.twilio.com) account with a voice-enabled number
- An [OpenAI](https://platform.openai.com) API key
- A publicly accessible URL (e.g. via [ngrok](https://ngrok.com) for local dev)

### Installation

```bash
git clone https://github.com/ArtradePro/q2c-voice-bot.git
cd q2c-voice-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable                   | Description                                  |
|----------------------------|----------------------------------------------|
| `TWILIO_ACCOUNT_SID`       | Twilio Account SID                           |
| `TWILIO_AUTH_TOKEN`        | Twilio Auth Token                            |
| `TWILIO_PHONE_NUMBER`      | Your Twilio phone number (E.164 format)      |
| `OPENAI_API_KEY`           | OpenAI API key                               |
| `OPENAI_MODEL`             | Model to use (default: `gpt-4o`)             |
| `APP_BASE_URL`             | Public URL of your deployed server           |
| `APP_HOST`                 | Bind host (default: `0.0.0.0`)               |
| `APP_PORT`                 | Bind port (default: `8000`)                  |
| `SPEECH_TIMEOUT`           | Seconds of silence before speech ends        |

### Running locally

```bash
# Start the app
python main.py

# In a separate terminal, expose it via ngrok
ngrok http 8000
```

Set the ngrok HTTPS URL as `APP_BASE_URL` in `.env`, then configure your Twilio
number's **Voice** webhook to:

```
POST https://<your-ngrok-url>/voice/incoming
```

Also set the **Status Callback URL** to:

```
POST https://<your-ngrok-url>/voice/status
```

---

## Project structure

```
q2c-voice-bot/
├── main.py                    # FastAPI app & Twilio webhook endpoints
├── config.py                  # Settings loaded from environment
├── requirements.txt
├── .env.example
├── bot/
│   ├── __init__.py
│   ├── conversation.py        # In-memory conversation state manager
│   ├── contract_generator.py  # Produces the formatted contract document
│   ├── llm_engine.py          # OpenAI GPT conversation driver
│   ├── quote_processor.py     # Quote data model & premium calculator
│   └── voice_handler.py       # Twilio TwiML response builders
└── tests/
    ├── test_conversation.py
    ├── test_contract_generator.py
    ├── test_main.py
    ├── test_quote_processor.py
    └── test_voice_handler.py
```

---

## Running tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## Coverage types & rates

| Type     | Monthly rate | Notes                        |
|----------|-------------|------------------------------|
| Life     | 0.20%       | 5% off ≥ 5 yrs; 10% off ≥ 10 yrs |
| Health   | 0.30%       | same discounts                |
| Auto     | 0.40%       | same discounts                |
| Property | 0.25%       | same discounts                |

---

## License

Proprietary — ArtradePro © 2026
