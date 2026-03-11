# Decision Log -- Trello Daily Agent

## 2026-03-11 -- Stateless Design with No Database
**Context**: The agent needs to produce daily reports from Trello board data. Options were to store historical data in a database for trend analysis or to fetch fresh data each run.
**Decision**: Fully stateless -- no database, no file storage, no persistent state between runs.
**Reasoning**: Eliminates infrastructure cost and maintenance. GitHub Actions provides free compute on a cron schedule. Trello itself is the source of truth. Historical tracking can be added later if needed.
**Impact**: Each run is independent. There is no way to compare today's board state with yesterday's without adding a persistence layer.

---

## 2026-03-11 -- OpenAI (gpt-4o-mini) for AI Analysis
**Context**: Needed an LLM to generate human-readable briefings from structured Trello JSON data. Considered OpenAI, Anthropic Claude, and open-source models.
**Decision**: OpenAI Chat Completions API with `gpt-4o-mini` as the default model.
**Reasoning**: `gpt-4o-mini` offers a strong cost-to-quality ratio for structured summarization. The OpenAI Python SDK is mature and well-documented. The model can be changed via the `OPENAI_MODEL` env var without code changes.
**Impact**: Requires an OpenAI API key and billing account. The `openai` Python package is a dependency.

---

## 2026-03-11 -- Meta WhatsApp Cloud API for Message Delivery
**Context**: Needed a way to deliver reports to team members. Options: email, Slack, Telegram, WhatsApp.
**Decision**: Meta WhatsApp Cloud API (free tier).
**Reasoning**: WhatsApp has near-universal adoption in the target user base (Indian teams). The Cloud API free tier allows up to 1,000 conversations/month, which is more than enough for twice-daily messages. No additional app installation required on the recipient's side.
**Impact**: Requires a Meta Developer account, a WhatsApp Business app, and a verified recipient number. The test token expires every 24 hours -- production use needs a permanent System User token.

---

## 2026-03-11 -- zoneinfo Over pytz for Timezone Handling
**Context**: The agent needs timezone-aware time comparisons for auto-detecting morning/evening mode and computing "today's midnight" for activity queries.
**Decision**: Use `zoneinfo.ZoneInfo` from Python's standard library (3.9+).
**Reasoning**: `zoneinfo` is part of the stdlib since Python 3.9, eliminating an external dependency. `pytz` has known API quirks (e.g., `localize()` vs. direct construction). Since the project targets Python 3.12, `zoneinfo` is the modern standard.
**Impact**: No additional dependency for timezone handling. Requires Python 3.9+.

---

## 2026-03-11 -- IST 2:00 PM Cutoff for Morning/Evening Detection
**Context**: The agent auto-detects whether to run a morning briefing or evening summary based on the current time. Needed a cutoff point.
**Decision**: If the current local hour is less than 14 (2:00 PM), run morning mode; otherwise, run evening mode.
**Reasoning**: The morning cron runs at 8:00 AM IST and evening at 9:00 PM IST. A 2:00 PM cutoff provides a wide margin for both scheduled runs and manual triggers at any time of day. It also makes manual testing intuitive -- run before 2 PM for morning, after for evening.
**Impact**: The `EVENING_CUTOFF_HOUR` constant in `main.py` controls this behavior. Configurable timezone via `TIMEZONE` env var.

---

## 2026-03-11 -- Truncate Card Descriptions to 100 Characters Before OpenAI
**Context**: Card descriptions on Trello can be very long (multi-paragraph specs, acceptance criteria, etc.). Sending full descriptions to OpenAI would consume significant tokens and increase cost.
**Decision**: Truncate all card descriptions to 100 characters with `...` suffix before including them in the OpenAI prompt.
**Reasoning**: The AI only needs a brief context of each card, not the full specification. 100 characters captures the first sentence or key phrase. This keeps token usage predictable and cost low, especially for boards with many cards.
**Impact**: The `MAX_DESCRIPTION_LENGTH` constant in `src/analyzer.py` controls the limit. Full descriptions are never sent to OpenAI.

---

## 2026-03-11 -- Message Splitting at Paragraph Boundaries
**Context**: WhatsApp has a 4,096-character message limit. AI-generated briefings can exceed this, especially for large boards.
**Decision**: Split messages at double-newline (paragraph) boundaries. If a single paragraph exceeds the limit, fall back to single-newline splits.
**Reasoning**: Splitting at paragraph boundaries preserves the readability of the message. Each section (overdue, due today, blockers, etc.) stays intact. This is more user-friendly than splitting at an arbitrary character count.
**Impact**: `_split_message()` in `src/whatsapp_sender.py` handles this. Split parts are sent sequentially with a 1-second delay between them.

---
