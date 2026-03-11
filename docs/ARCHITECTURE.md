# Architecture -- Trello Daily Agent
> Last updated: 2026-03-11

## System Overview

Trello Daily Agent is a stateless Python script that runs twice daily on GitHub Actions. It fetches project data from a Trello board, sends it to OpenAI for AI-powered analysis, and delivers the resulting briefing or summary to a WhatsApp recipient via Meta's Cloud API. The system has no database, no server, and no persistent state -- each run is fully independent.

The morning run produces a prioritized briefing (overdue tasks, blockers, upcoming work). The evening run adds today's activity log (card movements, comments, completions) to produce a progress summary.

## Component Map

### Entry Point -- `main.py`
- Parses CLI arguments (`--mode morning|evening` or auto-detect)
- Auto-detects morning vs. evening based on a 2:00 PM IST cutoff using `zoneinfo`
- Orchestrates the three-step pipeline: fetch -> analyze -> send
- Top-level error handler sends WhatsApp error notifications on failure

### Configuration -- `src/config.py`
- Loads environment variables from `.env` (local) or `os.environ` (CI)
- Returns a frozen `dataclass` (`Config`) with all credentials and settings
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

### WhatsApp Sender -- `src/whatsapp_sender.py`
- Wraps Meta WhatsApp Cloud API v21.0 (`https://graph.facebook.com/v21.0`)
- `send_message()` -- splits messages exceeding 4,096 chars at paragraph boundaries, sends sequentially with 1s delay
- `send_error_notification()` -- sends a short error alert; has its own try/except so notification failures do not mask the original error
- `_split_message()` -- splits at double newlines first, falls back to single newlines for oversized paragraphs

## Data Flow

### Morning Briefing (runs at 8:00 AM IST / 2:30 AM UTC)

```
GitHub Actions cron (2:30 UTC)
  |
  v
main.py --mode auto -> determines "morning" (hour < 14 IST)
  |
  v
trello_client.get_board_data(board_id)
  |-- GET /boards/{id}           -> board name
  |-- GET /boards/{id}/lists     -> all lists
  |-- GET /lists/{id}/cards      -> cards per list (with members, labels, due dates)
  |
  v
analyzer.generate_morning_briefing(board_data)
  |-- truncate card descriptions to 100 chars
  |-- POST OpenAI Chat Completions (system prompt + JSON board data)
  |
  v
whatsapp_sender.send_message(briefing_text)
  |-- split if > 4096 chars
  |-- POST /v21.0/{phone_id}/messages  (one per chunk)
  |
  v
WhatsApp message delivered to recipient
```

### Evening Summary (runs at 9:00 PM IST / 3:30 PM UTC)

```
GitHub Actions cron (15:30 UTC)
  |
  v
main.py --mode auto -> determines "evening" (hour >= 14 IST)
  |
  v
trello_client.get_board_data(board_id)        -> current board state
trello_client.get_board_activity(board_id, since_midnight_utc)
  |-- GET /boards/{id}/actions?since=...     -> today's actions (filtered to 9 types)
  |
  v
analyzer.generate_evening_summary(board_data, activity)
  |-- truncate descriptions, combine board data + activity as JSON
  |-- POST OpenAI Chat Completions
  |
  v
whatsapp_sender.send_message(summary_text)
  |
  v
WhatsApp message delivered to recipient
```

## Key Patterns

- **Stateless execution**: No database, no file storage, no memory between runs. Each run fetches fresh data and produces a self-contained message.
- **Fail-fast configuration**: All required env vars are validated at startup. Missing any variable immediately raises a `ValueError` with a descriptive message.
- **Error notification**: If any step fails, the top-level handler in `main.py` sends a WhatsApp error alert (best-effort) before exiting with code 1.
- **Rate-limit courtesy**: 100ms delay between Trello API calls; 1s delay between split WhatsApp message parts.
- **Token budget control**: Card descriptions are truncated to 100 characters before being sent to OpenAI. The model is instructed to keep responses under 3,800 characters.
- **Smart message splitting**: Messages are split at paragraph boundaries (double newlines) to avoid breaking mid-sentence. Falls back to single-newline splits for oversized paragraphs.
- **Timezone-aware auto-detection**: Uses `zoneinfo.ZoneInfo` (stdlib, Python 3.9+) to determine morning vs. evening based on configured timezone with a 2:00 PM cutoff.

## External Dependencies

| Service | API | Purpose |
|---------|-----|---------|
| Trello | REST API v1 | Board data and activity |
| OpenAI | Chat Completions | AI-generated briefings and summaries |
| Meta WhatsApp | Cloud API v21.0 | Message delivery |
| GitHub Actions | Cron scheduler | Twice-daily execution |

## Known Constraints

- **Single recipient**: The current implementation sends to one WhatsApp number only. Supporting multiple recipients would require looping over a list of numbers.
- **WhatsApp free tier**: Meta's free tier allows up to 1,000 service-initiated conversations per month and limits test recipients to verified numbers only.
- **Meta test token expiry**: The temporary access token from Meta expires every 24 hours. Production use requires a permanent System User token.
- **GitHub Actions cron jitter**: Scheduled runs can be delayed by up to 15 minutes.
- **Large boards**: Boards with many lists and cards will make many sequential Trello API calls (one per list). Very large boards may approach the 100 req/10s rate limit.
- **No retry logic**: Failed API calls (Trello, OpenAI, WhatsApp) are not retried. A failure results in an error notification and exit.
