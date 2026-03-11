# Changelog -- Trello Daily Agent

## 2026-03-11 -- Initial Build
- **What changed**: Built the complete Trello Daily Agent from scratch. Implemented all four modules: `config.py` (environment loading and validation), `trello_client.py` (Trello REST API client with board data and activity fetching), `analyzer.py` (OpenAI-powered morning briefing and evening summary generation), and `whatsapp_sender.py` (WhatsApp Cloud API sender with message splitting). Created `main.py` entry point with CLI argument parsing and automatic morning/evening detection. Set up GitHub Actions workflow with twice-daily cron schedule and manual trigger.
- **Why**: Automate daily project status reporting so team members receive Trello board updates via WhatsApp without manual effort.
- **Files affected**: `main.py`, `src/config.py`, `src/trello_client.py`, `src/analyzer.py`, `src/whatsapp_sender.py`, `.github/workflows/daily-agent.yml`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

---
