# Trello Daily Agent

An automated project management assistant that reads your Trello board twice a day and delivers AI-powered briefings via WhatsApp.

- **Morning (8:00 AM IST):** Overdue tasks, due today, prioritized to-dos, blockers, and upcoming items for the week.
- **Evening (9:00 PM IST):** Completed tasks, card movements, new comments, new cards, member activity, and board health stats.

Runs on GitHub Actions on a cron schedule. No server required.

---

## Prerequisites

You need accounts and API credentials from three services:

1. **Trello** -- a board you want to monitor
2. **OpenAI** -- for generating the AI-powered briefings
3. **Meta Developer (WhatsApp Cloud API)** -- for sending WhatsApp messages

---

## Setup

### 1. Trello API Credentials

1. Go to [https://trello.com/power-ups/admin](https://trello.com/power-ups/admin).
2. Create a new Power-Up (or use an existing one) to get your **API Key**.
3. On the same page, click the link to generate a **Token** -- authorize it for your account.
4. Find your **Board ID**: open your Trello board in a browser. The URL looks like `https://trello.com/b/AbCdEfGh/my-board-name`. The Board ID is the `AbCdEfGh` part.

You now have:
- `TRELLO_API_KEY`
- `TRELLO_TOKEN`
- `TRELLO_BOARD_ID`

### 2. OpenAI API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Create a new API key.
3. Make sure your account has billing enabled and sufficient credits.

You now have:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, defaults to `gpt-4o-mini`)

### 3. Meta WhatsApp Cloud API

1. Go to [https://developers.facebook.com](https://developers.facebook.com) and create a new app (type: Business).
2. Add the **WhatsApp** product to your app.
3. Go to **WhatsApp > API Setup** in the left sidebar.
4. Copy your **Temporary Access Token** (valid for 24 hours) or generate a permanent System User token for production use.
5. Copy the **Phone Number ID** shown on the API Setup page.
6. Under the **"To"** section, add your personal phone number as a verified recipient. You must verify it with a code sent via WhatsApp.

You now have:
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_RECIPIENT_NUMBER` (your phone number in international format without `+`, e.g., `919876543210`)

**Important:** The Meta test access token expires every 24 hours. For a persistent setup, create a System User in Meta Business Suite and generate a permanent token.

---

## Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/trello-agent.git
   cd trello-agent
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create your environment file:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and fill in all your API credentials.

5. Run the agent:
   ```bash
   # Morning briefing
   python main.py --mode morning

   # Evening summary
   python main.py --mode evening

   # Auto-detect based on current time
   python main.py
   ```

---

## GitHub Actions Deployment

The agent runs automatically via GitHub Actions on a cron schedule.

### Add Repository Secrets

1. Go to your repository on GitHub.
2. Navigate to **Settings > Secrets and variables > Actions**.
3. Click **New repository secret** and add each of these:

   | Secret Name                | Value                          |
   |----------------------------|--------------------------------|
   | `TRELLO_API_KEY`           | Your Trello API key            |
   | `TRELLO_TOKEN`             | Your Trello token              |
   | `TRELLO_BOARD_ID`          | Your Trello board ID           |
   | `OPENAI_API_KEY`           | Your OpenAI API key            |
   | `OPENAI_MODEL`             | `gpt-4o-mini` (or your choice) |
   | `WHATSAPP_ACCESS_TOKEN`    | Your Meta access token         |
   | `WHATSAPP_PHONE_NUMBER_ID` | Your WhatsApp phone number ID  |
   | `WHATSAPP_RECIPIENT_NUMBER`| Recipient number (e.g., `919876543210`) |

### Enable GitHub Actions

1. Go to the **Actions** tab in your repository.
2. If prompted, enable workflows.
3. The agent will run automatically at:
   - **8:00 AM IST** (2:30 AM UTC) -- morning briefing
   - **9:00 PM IST** (3:30 PM UTC) -- evening summary
4. You can also trigger a run manually from the Actions tab using the **"Run workflow"** button.

---

## Project Structure

```
.
├── .github/workflows/
│   └── daily-agent.yml      # GitHub Actions cron workflow
├── src/
│   ├── __init__.py
│   ├── config.py             # Environment variable loading and validation
│   ├── trello_client.py      # Trello REST API client
│   ├── analyzer.py           # OpenAI-powered briefing generator
│   └── whatsapp_sender.py    # WhatsApp Cloud API message sender
├── main.py                   # Entry point with CLI and auto-detection
├── requirements.txt          # Python dependencies
├── .env.example              # Template for environment variables
├── .gitignore
└── README.md
```

---

## Troubleshooting

### Missing Environment Variables
The agent validates all required environment variables at startup. If any are missing, you will see a clear error message listing which variables need to be set.

### WhatsApp Recipient Not Verified
Meta requires recipient phone numbers to be verified during development. Go to **WhatsApp > API Setup** in your Meta Developer dashboard and add/verify recipient numbers under the **"To"** section.

### WhatsApp Access Token Expired
The test access token from Meta expires every 24 hours. For production use, create a System User in Meta Business Suite and generate a permanent token.

### Trello API Rate Limits
The Trello API has a rate limit of 100 requests per 10 seconds per token. The agent includes a 0.1s delay between API calls to stay well within limits. If you have a very large board (many lists with many cards), you may need to increase the delay in `src/trello_client.py`.

### OpenAI Token Budget
The agent uses `gpt-4o-mini` by default, which is cost-effective. Card descriptions are truncated to 100 characters to reduce token usage. If you have a very large board, monitor your OpenAI usage dashboard.

### GitHub Actions Not Running
- Ensure Actions are enabled in your repository settings.
- Cron schedules in GitHub Actions can have delays of up to 15 minutes.
- Check the Actions tab for any failed runs and review the logs.

---

## License

MIT
