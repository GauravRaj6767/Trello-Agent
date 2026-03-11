# Decision Log -- Trello Daily Agent

## 2026-03-11 -- Multi-Recipient via WHATSAPP_NOTIFY_1/2/3 Env Vars
**Context**: Needed to support sending reports to multiple WhatsApp numbers. Options: comma-separated list in one env var, JSON array, or numbered env vars.
**Decision**: Use `WHATSAPP_NOTIFY_1`, `WHATSAPP_NOTIFY_2`, `WHATSAPP_NOTIFY_3` as separate env vars with fallback to legacy `WHATSAPP_RECIPIENT_NUMBER`.
**Reasoning**: This pattern was already proven in another working app. GitHub Actions secrets are easier to manage as individual values than parsing delimiters. Numbered vars make it obvious how many recipients are configured. Fallback preserves backward compatibility.
**Impact**: `Config.whatsapp_recipient_numbers` is now a `list[str]`. All sending functions iterate over this list. GitHub Actions workflow needs updated secrets.

---

## 2026-03-11 -- Retry at the Flow Level (Not Per-API-Call)
**Context**: Transient failures in Trello, OpenAI, or WhatsApp APIs caused the agent to fail entirely. Options: retry individual API calls with backoff, or retry the entire flow.
**Decision**: Retry the entire morning/evening flow up to 3 times with 30-second delays between attempts.
**Reasoning**: The flow is short (seconds) and fully idempotent -- re-fetching fresh data and re-generating the briefing is cheap. Flow-level retry is simpler than adding retry logic to each of the three API clients independently. It also handles unexpected failures in non-API code (e.g., JSON parsing, config issues that resolve on retry).
**Impact**: `run_with_retry()` in `main.py` wraps `run_morning()`/`run_evening()`. Individual API calls still fail immediately on error.

---

## 2026-03-11 -- Strip LLM Fluff at Post-Processing Level
**Context**: Despite system prompts saying "no preamble, no closing remarks," OpenAI models occasionally prepend "Sure, here is your briefing!" or append "Let me know if you need anything else." These lines waste WhatsApp character budget and look unprofessional.
**Decision**: Apply `_strip_llm_fluff()` post-processing in addition to prompt instructions. The function removes lines starting with known fluff prefixes (e.g., "sure", "here is", "let me know", "feel free").
**Reasoning**: Prompt instructions reduce but do not eliminate fluff. Post-processing provides a deterministic safety net. The prefix list is conservative (only matches clear preamble/postamble patterns) so it will not strip legitimate briefing content.
**Impact**: `_strip_llm_fluff()` in `src/analyzer.py` runs on every OpenAI response before truncation. The `_FLUFF_PREFIXES` tuple can be extended if new patterns appear.

---

## 2026-03-11 -- Empty Board Check Skips OpenAI Entirely
**Context**: When a Trello board has zero cards, sending empty JSON to OpenAI produced nonsensical briefings ("There are no tasks to report, but here are some suggestions...") and wasted API credits.
**Decision**: Check card count before calling OpenAI. If 0 cards (morning) or 0 cards + 0 activity (evening), send a short static message directly and return.
**Reasoning**: There is nothing for the AI to analyze on an empty board. A static message is faster, cheaper, and more predictable. The evening flow still calls OpenAI if there is activity (e.g., all cards were completed and archived today) even with 0 current cards, since the activity log has value.
**Impact**: `_total_cards()` helper in `main.py`. Short-circuit logic in `run_morning()` and `run_evening()`.

---

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
**Impact**: Requires a Meta Developer account, a WhatsApp Business app, and verified recipient numbers. The test token expires every 24 hours -- production use needs a permanent System User token.

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
**Reasoning**: The morning cron runs at 8:00 AM IST and evening at 9:00 PM IST. A 2:00 PM cutoff provides a wide margin for both scheduled runs and manual triggers at any time of day.
**Impact**: The `EVENING_CUTOFF_HOUR` constant in `main.py` controls this behavior. Configurable timezone via `TIMEZONE` env var.

---

## 2026-03-11 -- Truncate Card Descriptions to 100 Characters Before OpenAI
**Context**: Card descriptions on Trello can be very long. Sending full descriptions to OpenAI would consume significant tokens and increase cost.
**Decision**: Truncate all card descriptions to 100 characters with `...` suffix before including them in the OpenAI prompt.
**Reasoning**: The AI only needs a brief context of each card. 100 characters captures the first sentence or key phrase. Keeps token usage predictable and cost low.
**Impact**: The `MAX_DESCRIPTION_LENGTH` constant in `src/analyzer.py` controls the limit.

---

## 2026-03-11 -- Message Splitting at Paragraph Boundaries
**Context**: WhatsApp has a 4,096-character message limit. AI-generated briefings can exceed this.
**Decision**: Split messages at double-newline (paragraph) boundaries. If a single paragraph exceeds the limit, fall back to single-newline splits.
**Reasoning**: Splitting at paragraph boundaries preserves readability. Each section stays intact.
**Impact**: `_split_message()` in `src/whatsapp_sender.py` handles this. Split parts sent with 1s delay.

---
