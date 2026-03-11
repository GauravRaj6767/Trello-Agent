# Changelog -- Trello Daily Agent

## 2026-03-11 -- Multi-Recipient WhatsApp Delivery
- **What changed**: WhatsApp sender now iterates over a list of recipient numbers instead of sending to a single number. Config reads `WHATSAPP_NOTIFY_1`, `WHATSAPP_NOTIFY_2`, `WHATSAPP_NOTIFY_3` env vars, with fallback to legacy `WHATSAPP_RECIPIENT_NUMBER`. Error notifications also go to all recipients.
- **Why**: Multiple team members need to receive the daily reports directly.
- **Files affected**: `src/config.py`, `src/whatsapp_sender.py`, `.github/workflows/daily-agent.yml`

---

## 2026-03-11 -- Phone Number Normalization and wamid Logging
- **What changed**: Added `_normalize_number()` to strip spaces and ensure `+` prefix on phone numbers. Successful deliveries now log the WhatsApp message ID (wamid).
- **Why**: Inconsistent number formatting caused delivery failures. wamid logging aids debugging delivery issues.
- **Files affected**: `src/whatsapp_sender.py`

---

## 2026-03-11 -- Flow-Level Retry Logic
- **What changed**: Added `run_with_retry()` in `main.py` that wraps the entire morning/evening flow with up to 3 attempts and 30-second delays. Each failed attempt logs a full traceback. Final error notification includes attempt count.
- **Why**: Transient API failures (Trello, OpenAI, WhatsApp) were causing unnecessary full failures. Retrying the complete flow handles failures at any step.
- **Files affected**: `main.py`

---

## 2026-03-11 -- OpenAI Response Hardening
- **What changed**: `_call_openai()` now logs `finish_reason`, raises `ValueError` on empty content, strips LLM fluff lines via `_strip_llm_fluff()`, and hard-truncates at 3,800 chars at a paragraph boundary. System prompts updated with explicit "no preamble" instruction.
- **Why**: OpenAI occasionally returned empty responses, preamble text ("Sure, here is..."), or exceeded the character budget for WhatsApp messages.
- **Files affected**: `src/analyzer.py`

---

## 2026-03-11 -- Empty Board Short-Circuit
- **What changed**: Morning flow sends a "No open tasks" notice and skips OpenAI when the board has 0 cards. Evening flow sends a brief notice when 0 cards AND 0 activity; still runs AI if there is activity but 0 cards.
- **Why**: Sending empty JSON to OpenAI produced nonsensical output and wasted API credits.
- **Files affected**: `main.py`

---

## 2026-03-11 -- GitHub Actions Secrets Updated
- **What changed**: Workflow updated to pass `WHATSAPP_NOTIFY_1`, `WHATSAPP_NOTIFY_2`, `WHATSAPP_NOTIFY_3` instead of `WHATSAPP_RECIPIENT_NUMBER`.
- **Why**: Aligns with the new multi-recipient config pattern.
- **Files affected**: `.github/workflows/daily-agent.yml`

---

## 2026-03-11 -- Initial Build
- **What changed**: Built the complete Trello Daily Agent from scratch. Implemented all four modules: `config.py` (environment loading and validation), `trello_client.py` (Trello REST API client with board data and activity fetching), `analyzer.py` (OpenAI-powered morning briefing and evening summary generation), and `whatsapp_sender.py` (WhatsApp Cloud API sender with message splitting). Created `main.py` entry point with CLI argument parsing and automatic morning/evening detection. Set up GitHub Actions workflow with twice-daily cron schedule and manual trigger.
- **Why**: Automate daily project status reporting so team members receive Trello board updates via WhatsApp without manual effort.
- **Files affected**: `main.py`, `src/config.py`, `src/trello_client.py`, `src/analyzer.py`, `src/whatsapp_sender.py`, `.github/workflows/daily-agent.yml`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

---
