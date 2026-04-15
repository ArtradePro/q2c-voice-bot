"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # App
    app_base_url: str = "http://localhost:8000"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me"

    # Conversation
    max_call_duration_seconds: int = 600
    speech_timeout: int = 3


settings = Settings()
