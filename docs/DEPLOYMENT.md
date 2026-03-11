# Deployment -- Trello Daily Agent
> Last updated: 2026-03-11

## Overview

The agent runs on **GitHub Actions** using a cron schedule. There is no server, no container, and no cloud function. GitHub Actions provides the compute, and the workflow installs dependencies and runs the Python script on each trigger.

## GitHub Actions Workflow

**File**: `.github/workflows/daily-agent.yml`

### Schedule

| Trigger | Cron (UTC) | Local Time (IST) | Mode |
|---------|-----------|-------------------|------|
| Morning | `30 2 * * *` | 8:00 AM IST | Auto-detected as "morning" |
| Evening | `30 15 * * *` | 9:00 PM IST | Auto-detected as "evening" |
| Manual | `workflow_dispatch` | Any time | Auto-detected or override with `--mode` |

**Note**: GitHub Actions cron can be delayed by up to 15 minutes from the scheduled time.

### Workflow Steps

1. **Checkout** -- `actions/checkout@v4`
2. **Setup Python** -- `actions/setup-python@v5` with Python 3.12
3. **Install dependencies** -- `pip install -r requirements.txt`
4. **Run agent** -- `python main.py` with all secrets injected as env vars

The agent auto-detects morning vs. evening mode based on the current time in the configured timezone (IST by default, cutoff at 2:00 PM).

## Required GitHub Secrets

Add these in **Settings > Secrets and variables > Actions > New repository secret**:

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `TRELLO_API_KEY` | Yes | Trello Power-Up API key |
| `TRELLO_TOKEN` | Yes | Trello API token (authorized for your account) |
| `TRELLO_BOARD_ID` | Yes | ID of the Trello board to monitor (from the board URL) |
| `OPENAI_API_KEY` | Yes | OpenAI API key with billing enabled |
| `OPENAI_MODEL` | No | Model to use (default: `gpt-4o-mini`) |
| `WHATSAPP_ACCESS_TOKEN` | Yes | Meta WhatsApp Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | WhatsApp Business phone number ID |
| `WHATSAPP_NOTIFY_1` | Yes | First recipient phone number in international format (e.g., `+919876543210`) |
| `WHATSAPP_NOTIFY_2` | No | Second recipient phone number (optional) |
| `WHATSAPP_NOTIFY_3` | No | Third recipient phone number (optional) |

**Legacy**: `WHATSAPP_RECIPIENT_NUMBER` is still supported as a fallback if none of the `WHATSAPP_NOTIFY_*` vars are set, but new deployments should use the numbered vars.

The `TIMEZONE` variable is hardcoded to `Asia/Kolkata` in the workflow file. To change it, edit `.github/workflows/daily-agent.yml`.

## How to Add Secrets

1. Go to your GitHub repository
2. Click **Settings** (top nav bar)
3. Left sidebar: **Secrets and variables** > **Actions**
4. Click **New repository secret**
5. Enter the secret name (exact match from the table above) and its value
6. Click **Add secret**
7. Repeat for all required secrets

## Manual Trigger

1. Go to the **Actions** tab in your GitHub repository
2. Select the **Trello Daily Agent** workflow in the left sidebar
3. Click **Run workflow** (dropdown on the right)
4. Select the branch (usually `main` or `claude`)
5. Click **Run workflow**

The agent will auto-detect morning/evening mode based on the current time. There is no way to pass `--mode` via the manual trigger without modifying the workflow file.

## Local Testing

Before deploying to GitHub Actions, test locally:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env from the example
cp .env.example .env

# 3. Fill in all credentials in .env
#    Use WHATSAPP_NOTIFY_1 (and optionally _2, _3) for recipient numbers

# 4. Run with explicit mode
python main.py --mode morning    # test morning briefing
python main.py --mode evening    # test evening summary

# 5. Run with auto-detection
python main.py                   # uses current local time
```

Verify that:
- Configuration loads without errors
- Trello board data is fetched (check logs)
- OpenAI generates a response (check logs)
- WhatsApp message is received on your phone

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TRELLO_API_KEY` | -- | Trello API key from Power-Up admin |
| `TRELLO_TOKEN` | -- | Trello API token |
| `TRELLO_BOARD_ID` | -- | Board ID from Trello URL |
| `OPENAI_API_KEY` | -- | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `WHATSAPP_ACCESS_TOKEN` | -- | Meta WhatsApp Cloud API token |
| `WHATSAPP_PHONE_NUMBER_ID` | -- | WhatsApp phone number ID |
| `WHATSAPP_NOTIFY_1` | -- | First recipient number (e.g., `+919876543210`) |
| `WHATSAPP_NOTIFY_2` | -- | Second recipient number (optional) |
| `WHATSAPP_NOTIFY_3` | -- | Third recipient number (optional) |
| `WHATSAPP_RECIPIENT_NUMBER` | -- | Legacy single recipient (fallback only) |
| `TIMEZONE` | `Asia/Kolkata` | IANA timezone for morning/evening detection |

## Failure Behavior

- The agent retries the entire flow up to 3 times with 30-second delays between attempts.
- If all 3 attempts fail, it sends a WhatsApp error notification (to all recipients, best-effort) and exits with code 1.
- GitHub Actions will mark the workflow run as failed, visible in the Actions tab.
