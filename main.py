"""
Trello Daily Agent - Main entry point.

Automatically determines whether to run a morning briefing or evening summary
based on the current time in the configured timezone, or accepts an explicit
--mode argument. Fetches Trello board data, generates an AI-powered analysis,
and delivers it via WhatsApp.
"""

import argparse
import logging
import sys
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import load_config
from src.trello_client import get_board_data, get_board_activity, get_since_today_utc
from src.analyzer import generate_morning_briefing, generate_evening_summary
from src.whatsapp_sender import send_message, send_error_notification

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Cutoff hour in local time: before this hour = morning, at or after = evening
EVENING_CUTOFF_HOUR = 14  # 2:00 PM

# Retry configuration
MAX_ATTEMPTS = 3       # 1 initial + 2 retries
RETRY_DELAY_SEC = 30   # wait between attempts


def determine_mode(timezone_str: str) -> str:
    """
    Determine whether to run in morning or evening mode based on current local time.

    Args:
        timezone_str: IANA timezone string for the local time check.

    Returns:
        "morning" if before 2:00 PM local time, "evening" otherwise.
    """
    tz = ZoneInfo(timezone_str)
    now_local = datetime.now(tz)
    mode = "morning" if now_local.hour < EVENING_CUTOFF_HOUR else "evening"
    logger.info(
        "Current local time: %s -> mode: %s",
        now_local.strftime("%Y-%m-%d %H:%M %Z"),
        mode,
    )
    return mode


def run_morning(config) -> None:
    """Execute the morning briefing flow."""
    logger.info("=== Morning Briefing ===")

    # Step 1: Fetch board data
    logger.info("Fetching board data...")
    board_data = get_board_data(config, config.trello_board_id)

    # Step 2: Generate AI briefing
    logger.info("Generating morning briefing with AI...")
    briefing = generate_morning_briefing(config, board_data)
    logger.info("Briefing generated (%d chars)", len(briefing))

    # Step 3: Send via WhatsApp
    logger.info("Sending briefing via WhatsApp...")
    success = send_message(config, briefing)
    if success:
        logger.info("Morning briefing sent successfully!")
    else:
        logger.error("Failed to send morning briefing")
        raise RuntimeError("Failed to send morning briefing via WhatsApp")


def run_evening(config) -> None:
    """Execute the evening summary flow."""
    logger.info("=== Evening Summary ===")

    # Step 1: Fetch board data
    logger.info("Fetching board data...")
    board_data = get_board_data(config, config.trello_board_id)

    # Step 2: Fetch today's activity
    since = get_since_today_utc(config.timezone)
    logger.info("Fetching today's activity (since %s)...", since)
    activity = get_board_activity(config, config.trello_board_id, since)

    # Step 3: Generate AI summary
    logger.info("Generating evening summary with AI...")
    summary = generate_evening_summary(config, board_data, activity)
    logger.info("Summary generated (%d chars)", len(summary))

    # Step 4: Send via WhatsApp
    logger.info("Sending summary via WhatsApp...")
    success = send_message(config, summary)
    if success:
        logger.info("Evening summary sent successfully!")
    else:
        logger.error("Failed to send evening summary")
        raise RuntimeError("Failed to send evening summary via WhatsApp")


def run_with_retry(config, mode: str) -> None:
    """
    Run the agent in the given mode, retrying up to MAX_ATTEMPTS times on failure.

    Args:
        config: Loaded configuration object.
        mode: "morning" or "evening".
    """
    last_exception = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("--- Attempt %d/%d ---", attempt, MAX_ATTEMPTS)
            if mode == "morning":
                run_morning(config)
            else:
                run_evening(config)
            return  # success — exit retry loop

        except Exception as e:
            last_exception = e
            tb = traceback.format_exc()
            logger.error(
                "Attempt %d/%d failed — %s: %s\nTraceback:\n%s",
                attempt, MAX_ATTEMPTS,
                type(e).__name__, str(e),
                tb,
            )
            if attempt < MAX_ATTEMPTS:
                logger.info("Retrying in %d seconds...", RETRY_DELAY_SEC)
                time.sleep(RETRY_DELAY_SEC)

    # All attempts exhausted
    raise last_exception


def main() -> None:
    """Main entry point with CLI argument parsing and error handling."""
    parser = argparse.ArgumentParser(
        description="Trello Daily Agent - Morning briefings and evening summaries"
    )
    parser.add_argument(
        "--mode",
        choices=["morning", "evening"],
        default=None,
        help="Override auto-detected mode (morning or evening)",
    )
    args = parser.parse_args()

    config = None
    try:
        # Load and validate configuration
        config = load_config()
        logger.info("Configuration loaded successfully")

        # Determine run mode
        mode = args.mode if args.mode else determine_mode(config.timezone)

        run_with_retry(config, mode)
        logger.info("Agent run completed successfully")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        tb_summary = traceback.format_exc()
        logger.error(
            "All %d attempts failed. Final error — %s\nFull traceback:\n%s",
            MAX_ATTEMPTS, error_msg, tb_summary,
        )

        # Attempt to send error notification via WhatsApp
        if config is not None:
            logger.info("Sending error notification via WhatsApp...")
            send_error_notification(
                config,
                f"Failed after {MAX_ATTEMPTS} attempts.\n\nLast error: {error_msg}"
            )

        sys.exit(1)


if __name__ == "__main__":
    main()
