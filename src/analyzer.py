"""
AI-powered analysis module for generating Trello board briefings and summaries.

Uses the OpenAI API to produce WhatsApp-friendly morning briefings
and evening summaries based on board data and activity.
"""

import json
import logging

from openai import OpenAI

from src.config import Config

logger = logging.getLogger(__name__)

# Truncate card descriptions to keep token usage reasonable
MAX_DESCRIPTION_LENGTH = 100

# Phrases that indicate LLM preamble/postamble — lines starting with these are stripped
_FLUFF_PREFIXES = (
    "sure",
    "here is",
    "here's",
    "certainly",
    "of course",
    "let me know",
    "feel free",
    "i hope",
    "please note",
    "note:",
    "if you",
    "this briefing",
    "this summary",
    "below is",
    "above is",
)


def _strip_llm_fluff(text: str) -> str:
    """
    Remove common LLM preamble and postamble lines from the response.

    Strips lines like "Sure, here is your briefing!" or "Let me know if you
    need anything else." that are not part of the actual WhatsApp message.
    """
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        lower = line.strip().lower()
        if any(lower.startswith(prefix) for prefix in _FLUFF_PREFIXES):
            logger.debug("Stripped fluff line: %r", line)
            continue
        cleaned.append(line)
    # Remove leading/trailing blank lines left behind after stripping
    return "\n".join(cleaned).strip()


def _truncate_descriptions(board_data: dict) -> dict:
    """
    Create a copy of board_data with card descriptions truncated.

    Args:
        board_data: Full board data dict from trello_client.

    Returns:
        A new dict with descriptions capped at MAX_DESCRIPTION_LENGTH chars.
    """
    truncated = {
        "board_name": board_data["board_name"],
        "lists": [],
    }
    for lst in board_data["lists"]:
        truncated_cards = []
        for card in lst["cards"]:
            card_copy = dict(card)
            desc = card_copy.get("description", "")
            if len(desc) > MAX_DESCRIPTION_LENGTH:
                card_copy["description"] = desc[:MAX_DESCRIPTION_LENGTH] + "..."
            truncated_cards.append(card_copy)
        truncated["lists"].append({"name": lst["name"], "cards": truncated_cards})
    return truncated


def _call_openai(config: Config, system_prompt: str, user_message: str) -> str:
    """
    Send a chat completion request to the OpenAI API.

    Args:
        config: Application configuration with OpenAI credentials.
        system_prompt: The system message defining the assistant's behavior.
        user_message: The user message containing the data to analyze.

    Returns:
        The assistant's response text.
    """
    client = OpenAI(api_key=config.openai_api_key)

    logger.info("Sending request to OpenAI model=%s", config.openai_model)
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    # Guard against None content (e.g. content_filter or unexpected stop reason)
    finish_reason = response.choices[0].finish_reason
    result = response.choices[0].message.content

    if not result:
        raise ValueError(
            f"OpenAI returned empty content. finish_reason={finish_reason}, "
            f"model={config.openai_model}"
        )

    logger.info(
        "OpenAI response received (%d chars, finish_reason=%s)",
        len(result), finish_reason,
    )

    # Strip preamble/postamble fluff lines
    result = _strip_llm_fluff(result)
    logger.info("After fluff stripping: %d chars", len(result))

    # Hard-truncate at 3,800 chars at a clean paragraph boundary if LLM exceeded limit
    if len(result) > 3800:
        logger.warning(
            "OpenAI response exceeded 3,800 chars (%d chars) — truncating", len(result)
        )
        truncated = result[:3800]
        # Cut at last double newline to avoid mid-sentence truncation
        cutoff = truncated.rfind("\n\n")
        result = truncated[:cutoff].strip() if cutoff > 0 else truncated.strip()
        result += "\n\n(truncated)"
        logger.info("Truncated to %d chars", len(result))

    return result


def generate_morning_briefing(config: Config, board_data: dict) -> str:
    """
    Generate a WhatsApp-friendly morning briefing from board data.

    Analyzes overdue tasks, tasks due today, prioritized to-dos, blockers/stale
    cards, and upcoming items for the week.

    Args:
        config: Application configuration.
        board_data: Full board data dict from trello_client.get_board_data().

    Returns:
        Plain text morning briefing string ready for WhatsApp.
    """
    system_prompt = (
        "You are a project management assistant. Generate a WhatsApp-friendly "
        "morning briefing based on the Trello board data provided.\n\n"
        "Include these sections with emoji headers:\n"
        "- \U0001f534 Overdue tasks (due date passed, not marked complete)\n"
        "- \U0001f7e1 Due today tasks\n"
        "- \U0001f4cb Prioritized to-do list across all lists "
        "(infer priority from labels, due dates, list position)\n"
        "- \U0001f6a7 Blockers or stale cards (no activity in 7+ days, "
        "still in active lists)\n"
        "- \U0001f4c5 Upcoming this week (due in next 7 days)\n\n"
        "Keep your response under 3,800 characters total. "
        "Use plain text, no markdown formatting. Use emojis for section headers. "
        "Output ONLY the briefing itself — no greeting, no preamble, no closing remarks."
    )

    truncated_data = _truncate_descriptions(board_data)
    user_message = json.dumps(truncated_data, indent=None)

    return _call_openai(config, system_prompt, user_message)


def generate_evening_summary(
    config: Config, board_data: dict, activity: list
) -> str:
    """
    Generate a WhatsApp-friendly evening summary from board data and activity.

    Summarizes completed tasks, card movements, comments, new cards,
    member activity, and overall board health.

    Args:
        config: Application configuration.
        board_data: Full board data dict from trello_client.get_board_data().
        activity: List of action dicts from trello_client.get_board_activity().

    Returns:
        Plain text evening summary string ready for WhatsApp.
    """
    system_prompt = (
        "You are a project management assistant. Generate a WhatsApp-friendly "
        "evening summary based on the Trello board data and today's activity.\n\n"
        "Include these sections with emoji headers:\n"
        "- \u2705 Completed today\n"
        "- \U0001f504 Cards moved (list transitions)\n"
        "- \U0001f4ac New comments (summarize)\n"
        "- \U0001f195 New cards created\n"
        "- \U0001f465 Member activity (who did what)\n"
        "- \U0001f4ca Board health (total cards, cards per list, overall progress)\n\n"
        "Keep your response under 3,800 characters total. "
        "Use plain text, no markdown formatting. Use emojis for section headers. "
        "Output ONLY the summary itself — no greeting, no preamble, no closing remarks."
    )

    truncated_data = _truncate_descriptions(board_data)
    user_message = json.dumps(
        {"board_data": truncated_data, "activity": activity}, indent=None
    )

    return _call_openai(config, system_prompt, user_message)
