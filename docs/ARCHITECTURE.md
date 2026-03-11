# Architecture -- Trello Daily Agent
> Last updated: 2026-03-11

## System Overview

Trello Daily Agent is a stateless Python script that runs twice daily on GitHub Actions. It fetches project data from a Trello board, sends it to OpenAI for AI-powered analysis, and delivers the resulting briefing or summary to multiple WhatsApp recipients via Meta's Cloud API. The system has no database, no server, and no persistent state -- each run is fully independent.

The morning run produces a prioritized briefing (overdue tasks, blockers, upcoming work). The evening run adds today's activity log (card movements, comments, completions) to produce a progress summary. Both flows include an empty-board short-circuit that skips the OpenAI call when there is nothing to analyze.

## Component Map

### Entry Point -- `main.py`
- Parses CLI arguments (`--mode morning|evening` or auto-detect)
- Auto-detects morning vs. evening based on a 2:00 PM cutoff using `zoneinfo`
- Orchestrates the pipeline: fetch -> (empty check) -> analyze -> send
- **Retry layer**: `run_with_retry()` wraps the entire flow with up to 3 attempts and a 30-second delay between retries. Per-attempt tracebacks are logged.
- **Empty board handling**:
  - Morning: if 0 cards, sends a "No open tasks" notice and skips OpenAI entirely
  - Evening: if 0 cards AND 0 activity, sends a brief notice and skips OpenAI. If 0 cards but activity > 0, still runs the AI summary.
- Top-level error handler sends WhatsApp error notifications (to all recipients) on final failure, including the attempt count

### Configuration -- `src/config.py`
- Loads environment variables from `.env` (local) or `os.environ` (CI)
- Returns a frozen `dataclass` (`Config`) with all credentials and settings
- **Multi-recipient support**: reads `WHATSAPP_NOTIFY_1`, `WHATSAPP_NOTIFY_2`, `WHATSAPP_NOTIFY_3` into a `whatsapp_recipient_numbers` list. Falls back to legacy `WHATSAPP_RECIPIENT_NUMBER` if none of the new vars are set.
- Validates all required variables at startup; fails fast with a clear error listing missing vars
- Defaults: `OPENAI_MODEL` = `gpt-4o-mini`, `TIMEZONE` = `Asia/Kolkata`

### Trello Client -- `src/trello_client.py`
- Wraps Trello REST API v1 (`https://api.trello.com/1`)
- `get_board_data()` -- fetches board name, all lists, and all cards with members/labels/due dates
- `get_board_activity()` -- fetches today's actions filtered to 9 meaningful action types
- `get_since_today_utc()` -- computes local midnight as UTC ISO string for the activity query
- Includes 100ms delay between API calls to respect Trello rate limits (100 req / 10s)

### AI Analyzer -- `src/analyzer.py`
- Wraps OpenAI Chat Completions API
- `generate_morning_briefing()` -- system prompt requests overdue/due-today/prioritized/blockers/upcoming sections
- `generate_evening_summary()` -- system prompt requests completed/moved/comments/new/member-activity/health sections
- Truncates card descriptions to 100 characters before sending to OpenAI to control token usage
- Uses `temperature=0.7`, `max_tokens=2000`; responses are plain text with emoji headers (no markdown)
- **Response hardening pipeline** (in `_call_openai()`):
  1. `finish_reason` is logged on every response
  2. Raises `ValueError` if the response content is `None` or empty
  3. `_strip_llm_fluff()` removes preamble/postamble lines (e.g., "Sure, here is...", "Let me know if...")
  4. Hard truncation at 3,800 chars at a paragraph boundary with `(truncated)` marker
- System prompts include: "Output ONLY the briefing/summary itself -- no greeting, no preamble, no closing remarks"

### WhatsApp Sender -- `src/whatsapp_sender.py`
- Wraps Meta WhatsApp Cloud API v21.0 (`https://graph.facebook.com/v21.0`)
- **Multi-recipient delivery**: `send_message()` iterates over all numbers in `config.whatsapp_recipient_numbers`, sending each chunk to each recipient
- `_normalize_number()` -- strips spaces and ensures `+` prefix on phone numbers
- `_send_to_number()` -- sends to a single number and logs the `wamid` on successful delivery
- `_split_message()` -- splits at double newlines first, falls back to single newlines for oversized paragraphs
- `send_error_notification()` -- sends error alerts to all recipients; has its own try/except so notification failures do not mask the original error

## Data Flow

### Morning Briefing (runs at 8:00 AM IST / 2:30 AM UTC)

```
GitHub Actions cron (2:30 UTC)
  |
  v
main.py -> determines "morning" (hour < 14)
  |
  v
run_with_retry (up to 3 attempts, 30s between retries)
  |
  v
trello_client.get_board_data(board_id)
  |-- GET /boards/{id}           -> board name
  |-- GET /boards/{id}/lists     -> all lists
  |-- GET /lists/{id}/cards      -> cards per list
  |
  v
[0 cards?] --yes--> send "No open tasks" notice to all recipients -> done
  |
  no
  |
  v
analyzer.generate_morning_briefing(board_data)
  |-- truncate descriptions to 100 chars
  |-- POST OpenAI Chat Completions
  |-- strip fluff -> truncate to 3800 chars
  |
  v
whatsapp_sender.send_message(briefing_text)
  |-- split if > 4096 chars
  |-- POST /v21.0/{phone_id}/messages per recipient per chunk
  |
  v
WhatsApp messages delivered to all recipients
```

### Evening Summary (runs at 9:00 PM IST / 3:30 PM UTC)

```
GitHub Actions cron (15:30 UTC)
  |
  v
main.py -> determines "evening" (hour >= 14)
  |
  v
run_with_retry (up to 3 attempts, 30s between retries)
  |
  v
trello_client.get_board_data(board_id)        -> current board state
trello_client.get_board_activity(board_id, since_midnight_utc)
  |-- GET /boards/{id}/actions?since=...     -> today's actions
  |
  v
[0 cards AND 0 activity?] --yes--> send brief notice -> done
  |
  no (cards > 0 OR activity > 0)
  |
  v
analyzer.generate_evening_summary(board_data, activity)
  |-- truncate descriptions, combine board data + activity as JSON
  |-- POST OpenAI Chat Completions
  |-- strip fluff -> truncate to 3800 chars
  |
  v
whatsapp_sender.send_message(summary_text)
  |
  v
WhatsApp messages delivered to all recipients
```

## Key Patterns

- **Stateless execution**: No database, no file storage, no memory between runs. Each run fetches fresh data and produces a self-contained message.
- **Flow-level retry**: `run_with_retry()` wraps the entire morning/evening flow (not individual API calls) with 3 attempts and 30s delay. This catches transient failures across any step.
- **Empty board short-circuit**: Skips the OpenAI call entirely when there is nothing meaningful to analyze, saving cost and avoiding nonsensical AI output.
- **LLM response hardening**: Defense-in-depth approach -- system prompts instruct "no preamble," post-processing strips fluff lines anyway, and a hard truncation cap prevents oversized messages.
- **Multi-recipient delivery**: All messages (briefings, summaries, errors) are sent to every configured recipient number.
- **Fail-fast configuration**: All required env vars are validated at startup. Missing any variable immediately raises a `ValueError` with a descriptive message.
- **Error notification**: If all retry attempts fail, the top-level handler sends a WhatsApp error alert (to all recipients, best-effort) before exiting with code 1.
- **Rate-limit courtesy**: 100ms delay between Trello API calls; 1s delay between split WhatsApp message parts.
- **Token budget control**: Card descriptions truncated to 100 chars. Model instructed to keep responses under 3,800 chars. Hard truncation enforced post-response.
- **Smart message splitting**: Messages split at paragraph boundaries (double newlines) to avoid breaking mid-sentence.
- **Timezone-aware auto-detection**: Uses `zoneinfo.ZoneInfo` (stdlib, Python 3.9+) with a 2:00 PM cutoff.

## External Dependencies

| Service | API | Purpose |
|---------|-----|---------|
| Trello | REST API v1 | Board data and activity |
| OpenAI | Chat Completions | AI-generated briefings and summaries |
| Meta WhatsApp | Cloud API v21.0 | Message delivery |
| GitHub Actions | Cron scheduler | Twice-daily execution |

## Known Constraints

- **WhatsApp free tier**: Meta's free tier allows up to 1,000 service-initiated conversations per month and limits test recipients to verified numbers only.
- **Meta test token expiry**: The temporary access token from Meta expires every 24 hours. Production use requires a permanent System User token.
- **GitHub Actions cron jitter**: Scheduled runs can be delayed by up to 15 minutes.
- **Large boards**: Boards with many lists and cards will make many sequential Trello API calls (one per list). Very large boards may approach the 100 req/10s rate limit.
- **Max 3 recipients**: The current config supports up to 3 WhatsApp recipient numbers via `WHATSAPP_NOTIFY_1/2/3`. Adding more would require a code change.
