"""
Trello API client for fetching board data and activity.

Uses the Trello REST API to retrieve board information, lists, cards,
and recent activity for generating daily briefings and summaries.
"""

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from src.config import Config

logger = logging.getLogger(__name__)

TRELLO_API_BASE = "https://api.trello.com/1"

# Small delay between consecutive API calls to avoid rate limiting
API_CALL_DELAY = 0.1

# Action types we care about for activity tracking
MEANINGFUL_ACTION_TYPES = {
    "updateCard",
    "createCard",
    "commentCard",
    "addMemberToCard",
    "removeMemberFromCard",
    "addAttachmentToCard",
    "deleteCard",
    "moveCardToBoard",
    "updateCheckItemStateOnCard",
}


def _trello_get(url: str, params: dict) -> dict | list:
    """
    Make a GET request to the Trello API with a small delay.

    Args:
        url: Full Trello API URL.
        params: Query parameters including key and token.

    Returns:
        Parsed JSON response.

    Raises:
        requests.HTTPError: If the API returns an error status.
    """
    time.sleep(API_CALL_DELAY)
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _build_auth_params(config: Config) -> dict:
    """Build the standard Trello auth query parameters."""
    return {"key": config.trello_api_key, "token": config.trello_token}


def get_board_data(config: Config, board_id: str) -> dict:
    """
    Fetch complete board data including all lists and their cards.

    Args:
        config: Application configuration with Trello credentials.
        board_id: The Trello board ID to fetch.

    Returns:
        Structured dict with board_name, and lists containing cards.
    """
    auth = _build_auth_params(config)

    # Fetch board name
    logger.info("Fetching board info for board_id=%s", board_id)
    board_info = _trello_get(f"{TRELLO_API_BASE}/boards/{board_id}", params=auth)
    board_name = board_info.get("name", "Unknown Board")

    # Fetch all lists on the board
    logger.info("Fetching lists for board '%s'", board_name)
    lists = _trello_get(f"{TRELLO_API_BASE}/boards/{board_id}/lists", params=auth)

    result_lists = []
    for lst in lists:
        # Fetch cards for each list with member details
        card_params = {
            **auth,
            "members": "true",
            "member_fields": "fullName",
            "fields": "name,desc,due,dueComplete,labels,idMembers,shortUrl,dateLastActivity",
        }
        logger.info("Fetching cards for list '%s'", lst["name"])
        cards = _trello_get(
            f"{TRELLO_API_BASE}/lists/{lst['id']}/cards", params=card_params
        )

        result_cards = []
        for card in cards:
            # Extract label names, falling back to color if no name set
            labels = []
            for label in card.get("labels", []):
                label_name = label.get("name") or label.get("color", "")
                if label_name:
                    labels.append(label_name)

            # Extract member full names
            members = [m.get("fullName", "") for m in card.get("members", [])]

            result_cards.append(
                {
                    "name": card.get("name", ""),
                    "description": card.get("desc", ""),
                    "due": card.get("due"),
                    "due_complete": card.get("dueComplete", False),
                    "labels": labels,
                    "members": members,
                    "url": card.get("shortUrl", ""),
                    "last_activity": card.get("dateLastActivity", ""),
                }
            )

        result_lists.append({"name": lst["name"], "cards": result_cards})

    logger.info(
        "Board data fetched: %d lists, %d total cards",
        len(result_lists),
        sum(len(l["cards"]) for l in result_lists),
    )

    return {"board_name": board_name, "lists": result_lists}


def _generate_action_details(action: dict) -> str:
    """
    Generate a human-readable summary of a Trello action.

    Args:
        action: Raw Trello action dict from the API.

    Returns:
        A short human-readable description of what happened.
    """
    action_type = action.get("type", "")
    data = action.get("data", {})

    if action_type == "updateCard":
        list_before = data.get("listBefore")
        list_after = data.get("listAfter")
        if list_before and list_after:
            return f"moved from '{list_before['name']}' to '{list_after['name']}'"

        old = data.get("old", {})
        if "due" in old:
            return "due date changed"
        if old.get("dueComplete") is not None:
            if data.get("card", {}).get("dueComplete"):
                return "marked as complete"
            return "marked as incomplete"

        return "card updated"

    elif action_type == "createCard":
        list_name = data.get("list", {}).get("name", "unknown")
        return f"created in list '{list_name}'"

    elif action_type == "commentCard":
        text = data.get("text", "")
        truncated = text[:100] + "..." if len(text) > 100 else text
        return f"commented: '{truncated}'"

    elif action_type == "addMemberToCard":
        member_name = data.get("member", {}).get("fullName", "unknown")
        return f"added member {member_name}"

    elif action_type == "removeMemberFromCard":
        member_name = data.get("member", {}).get("fullName", "unknown")
        return f"removed member {member_name}"

    elif action_type == "updateCheckItemStateOnCard":
        check_item_name = data.get("checkItem", {}).get("name", "unknown")
        return f"checked off '{check_item_name}'"

    elif action_type == "addAttachmentToCard":
        return "attachment added"

    elif action_type == "deleteCard":
        return "card deleted"

    elif action_type == "moveCardToBoard":
        return "card moved to board"

    return action_type


def get_board_activity(config: Config, board_id: str, since: str) -> list:
    """
    Fetch recent board activity since a given timestamp.

    Args:
        config: Application configuration with Trello credentials.
        board_id: The Trello board ID.
        since: ISO timestamp string; only actions after this time are returned.

    Returns:
        List of simplified action dicts with type, member, card_name,
        details, and timestamp.
    """
    auth = _build_auth_params(config)
    params = {**auth, "since": since, "limit": 1000}

    logger.info("Fetching board activity since %s", since)
    actions = _trello_get(
        f"{TRELLO_API_BASE}/boards/{board_id}/actions", params=params
    )

    results = []
    for action in actions:
        action_type = action.get("type", "")
        if action_type not in MEANINGFUL_ACTION_TYPES:
            continue

        member_creator = action.get("memberCreator", {})
        card = action.get("data", {}).get("card", {})

        results.append(
            {
                "type": action_type,
                "member": member_creator.get("fullName", "Unknown"),
                "card_name": card.get("name", "Unknown card"),
                "details": _generate_action_details(action),
                "timestamp": action.get("date", ""),
            }
        )

    logger.info("Found %d meaningful actions", len(results))
    return results


def get_since_today_utc(timezone_str: str = "Asia/Kolkata") -> str:
    """
    Compute today's midnight in the given timezone and return as UTC ISO string.

    This is used as the 'since' parameter for the Trello activity API to fetch
    only today's actions.

    Args:
        timezone_str: IANA timezone string (default: Asia/Kolkata).

    Returns:
        UTC ISO 8601 timestamp string for today's midnight in the given timezone.
    """
    tz = ZoneInfo(timezone_str)
    now_local = datetime.now(tz)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_utc = midnight_local.astimezone(ZoneInfo("UTC"))
    return midnight_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
