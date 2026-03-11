"""
Configuration module for the Trello Daily Agent.

Loads environment variables from .env file (local dev) or from
os.environ (GitHub Actions). Validates all required variables are present.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env file if it exists (no-op in GitHub Actions where env vars are injected)
load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable configuration object holding all required settings."""

    trello_api_key: str
    trello_token: str
    trello_board_id: str
    openai_api_key: str
    openai_model: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_recipient_numbers: list[str]  # one or more recipients
    timezone: str


def load_config() -> Config:
    """
    Load and validate configuration from environment variables.

    Returns:
        Config: Validated configuration object.

    Raises:
        ValueError: If any required environment variable is missing.
    """
    required_vars = [
        "TRELLO_API_KEY",
        "TRELLO_TOKEN",
        "TRELLO_BOARD_ID",
        "OPENAI_API_KEY",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please set them in your .env file or GitHub Actions secrets."
        )

    # Collect recipient numbers: WHATSAPP_NOTIFY_1, WHATSAPP_NOTIFY_2, WHATSAPP_NOTIFY_3
    # Fall back to legacy WHATSAPP_RECIPIENT_NUMBER if none of the new vars are set
    recipient_numbers = [
        os.environ[key]
        for key in ("WHATSAPP_NOTIFY_1", "WHATSAPP_NOTIFY_2", "WHATSAPP_NOTIFY_3")
        if os.environ.get(key)
    ]
    if not recipient_numbers:
        legacy = os.environ.get("WHATSAPP_RECIPIENT_NUMBER")
        if not legacy:
            raise ValueError(
                "At least one recipient number is required. Set WHATSAPP_NOTIFY_1 "
                "(and optionally WHATSAPP_NOTIFY_2, WHATSAPP_NOTIFY_3) in your environment."
            )
        recipient_numbers = [legacy]

    return Config(
        trello_api_key=os.environ["TRELLO_API_KEY"],
        trello_token=os.environ["TRELLO_TOKEN"],
        trello_board_id=os.environ["TRELLO_BOARD_ID"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        whatsapp_access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
        whatsapp_phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
        whatsapp_recipient_numbers=recipient_numbers,
        timezone=os.environ.get("TIMEZONE", "Asia/Kolkata"),
    )
