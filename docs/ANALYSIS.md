# Analysis -- Trello Daily Agent
> Last updated: 2026-03-11

## What the App Does

Trello Daily Agent is an automated project management assistant that monitors a Trello board and delivers AI-generated status updates via WhatsApp. It runs twice daily on a cron schedule (no server required) and produces two types of reports:

1. **Morning Briefing (8:00 AM IST)** -- A prioritized overview of the board's current state to help the team plan their day.
2. **Evening Summary (9:00 PM IST)** -- A recap of the day's activity to keep stakeholders informed of progress.

The goal is to eliminate the need for manual status checks. Team members receive a concise, actionable WhatsApp message without opening Trello.

## Target Audience

- Project managers who want automated daily status updates
- Small development teams (up to ~5 members) using Trello for task tracking
- Stakeholders who prefer WhatsApp over email or Slack for quick updates

## Functional Requirements

### Morning Briefing
- Fetch all lists and cards from the configured Trello board
- Identify overdue tasks (due date passed, not marked complete)
- Identify tasks due today
- Generate a prioritized to-do list (inferred from labels, due dates, list position)
- Flag blockers and stale cards (no activity in 7+ days in active lists)
- List items due in the next 7 days
- Deliver as a single WhatsApp message with emoji section headers

### Evening Summary
- Fetch all lists and cards (current board state)
- Fetch today's board activity (card moves, comments, completions, new cards, member changes)
- Summarize completed tasks
- Summarize card movements between lists
- Summarize new comments and new cards
- Report per-member activity
- Report board health (total cards, cards per list, overall progress)
- Deliver as a single WhatsApp message with emoji section headers

### Auto-Detection
- Automatically determine morning vs. evening mode based on the current time in the configured timezone
- Allow explicit `--mode` override via CLI argument

### Error Handling
- Validate all configuration at startup
- Send a WhatsApp error notification if any step fails
- Exit with non-zero code on failure for GitHub Actions visibility

## Non-Functional Requirements

- **Stateless**: No database, no persistent storage, no memory between runs. Each execution is fully independent.
- **Scheduled**: Runs automatically via GitHub Actions cron. No server to maintain.
- **Reliable delivery**: Messages are delivered via WhatsApp Cloud API with error detection and notification.
- **Cost-efficient**: Uses `gpt-4o-mini` by default and truncates card descriptions to 100 chars to minimize OpenAI token usage.
- **Timezone-aware**: All time-based logic uses `zoneinfo` with a configurable IANA timezone (default: `Asia/Kolkata`).
- **Low maintenance**: Only requires valid API credentials. No code changes needed for normal operation.

## Constraints and Assumptions

### WhatsApp Free Tier Limits
- Meta's free tier allows 1,000 service-initiated conversations per month
- During development, only verified phone numbers can receive messages
- The temporary test access token expires every 24 hours (permanent token requires a System User in Meta Business Suite)
- Single message limit: 4,096 characters (the agent splits longer messages automatically)

### OpenAI Token Budget
- Card descriptions are truncated to 100 characters before sending to OpenAI
- The system prompt instructs the model to keep responses under 3,800 characters
- `max_tokens` is capped at 2,000
- Default model is `gpt-4o-mini` (cost-effective for structured summarization tasks)

### Trello API Rate Limits
- Trello allows 100 requests per 10 seconds per API token
- The agent adds a 100ms delay between consecutive calls
- Each list on the board requires one API call to fetch its cards, so boards with many lists will use more of the rate budget

### GitHub Actions
- Cron schedule can be delayed by up to 15 minutes
- The workflow uses `ubuntu-latest` with Python 3.12
- All secrets are injected as environment variables at runtime
- Manual trigger is available via `workflow_dispatch`

### Single Recipient
- The current design sends to one WhatsApp number only
- Supporting multiple recipients would require code changes (loop over a list of numbers)
