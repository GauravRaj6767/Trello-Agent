"""
WhatsApp Cloud API sender module.

Sends plain text messages via the Meta WhatsApp Cloud API, with automatic
message splitting for long messages and error notification support.
"""

import logging
import time

import requests

from src.config import Config

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"

# WhatsApp message character limit
MAX_MESSAGE_LENGTH = 4096

# Delay between sending split message parts (seconds)
SPLIT_SEND_DELAY = 1


def _split_message(text: str) -> list[str]:
    """
    Split a long message into WhatsApp-safe chunks.

    Splits at double newlines or emoji section headers. Never splits
    mid-sentence. Each chunk will be under MAX_MESSAGE_LENGTH characters.

    Args:
        text: The full message text to split.

    Returns:
        List of message chunks, each under the character limit.
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    # Split on double newlines first (natural paragraph breaks)
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit, start a new chunk
        test_addition = (
            current_chunk + "\n\n" + paragraph if current_chunk else paragraph
        )

        if len(test_addition) > MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # If a single paragraph exceeds the limit, split on single newlines
            if len(paragraph) > MAX_MESSAGE_LENGTH:
                lines = paragraph.split("\n")
                current_chunk = ""
                for line in lines:
                    test_line = (
                        current_chunk + "\n" + line if current_chunk else line
                    )
                    if len(test_line) > MAX_MESSAGE_LENGTH:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line
                    else:
                        current_chunk = test_line
            else:
                current_chunk = paragraph
        else:
            current_chunk = test_addition

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _normalize_number(number: str) -> str:
    """Normalize a phone number to international format with + prefix."""
    cleaned = number.replace(" ", "")
    return cleaned if cleaned.startswith("+") else f"+{cleaned}"


def _send_to_number(config: Config, to: str, text: str) -> bool:
    """
    Send a single text message to one recipient via the WhatsApp Cloud API.

    Args:
        config: Application configuration with WhatsApp credentials.
        to: Recipient phone number (will be normalized).
        text: Message text to send (must be under 4096 chars).

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    normalized = _normalize_number(to)
    url = f"{WHATSAPP_API_URL}/{config.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {config.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": normalized,
        "type": "text",
        "text": {"body": text},
    }

    logger.info("Sending WhatsApp message to %s...", normalized)

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        result = response.json()
        if response.ok:
            wamid = (result.get("messages") or [{}])[0].get("id", "unknown")
            logger.info("Delivered to %s — wamid: %s", normalized, wamid)
            return True
        else:
            logger.error(
                "WhatsApp API error for %s: status=%d, response=%s",
                normalized,
                response.status_code,
                result,
            )
            return False
    except requests.RequestException as e:
        logger.error("WhatsApp API request failed for %s: %s", normalized, str(e))
        return False


def send_message(config: Config, text: str) -> bool:
    """
    Send a text message to all configured recipients, splitting if necessary.

    If the message exceeds 4,096 characters, it is split at paragraph
    breaks (double newlines). Each part is sent sequentially per recipient
    with a 1-second delay between parts.

    Args:
        config: Application configuration with WhatsApp credentials.
        text: The full message text to send.

    Returns:
        True if all parts were sent to all recipients successfully.
    """
    chunks = _split_message(text)
    if len(chunks) > 1:
        logger.info("Message split into %d parts for sending", len(chunks))

    all_success = True
    for number in config.whatsapp_recipient_numbers:
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(SPLIT_SEND_DELAY)
            logger.info(
                "Sending part %d/%d to %s (%d chars)",
                i + 1, len(chunks), number, len(chunk),
            )
            if not _send_to_number(config, number, chunk):
                all_success = False
                logger.error("Failed to send part %d/%d to %s", i + 1, len(chunks), number)

    return all_success


def send_error_notification(config: Config, error_message: str) -> None:
    """
    Send an error notification via WhatsApp to all recipients.

    This method has its own error handling so a failure to send the
    notification does not mask the original error.

    Args:
        config: Application configuration with WhatsApp credentials.
        error_message: Description of the error that occurred.
    """
    notification_text = (
        "⚠️ Trello Agent Error\n\n"
        f"{error_message}\n\n"
        "Check GitHub Actions logs for details."
    )

    try:
        for number in config.whatsapp_recipient_numbers:
            _send_to_number(config, number, notification_text)
    except Exception as e:
        logger.error(
            "Failed to send error notification via WhatsApp: %s", str(e)
        )
