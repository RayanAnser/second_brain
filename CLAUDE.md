# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal AI companion Telegram bot (Sprint 2). It receives text and voice messages in French, transcribes voice via Groq Whisper, responds via Claude, and has a memory system backed by local Markdown files.

## Running the bot

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python companion.py
```

## Required environment variables (`.env`)

```
TELEGRAM_TOKEN=...
ANTHROPIC_API_KEY=...
GROQ_API_KEY=...
MEMORY_DIR=./memory        # optional, defaults to ./memory
```

Note: `requirements.txt` is behind the actual code — `companion.py` also imports `groq` and `python-dotenv`, which must be installed.

## Working rules

Before answering any question about the code:
1. Read the relevant file to verify what actually exists
2. Test hypotheses with grep, ast.parse, or Python execution
3. Never assert something without having verified it in the code

## Architecture

`companion.py` is the single entry point. State dicts:
- `conversations` — per-user message history sent to Claude on every turn
- `staged_captures` — captures noted mid-conversation, persisted to `memory/staging.json`
- `pending_save_ops` — result of `save_intelligently()` waiting for user confirmation
- `pending_user_update` — user.md patch waiting for confirmation (via `/update`)
- `session_logs` — raw transcript of the current session

**System prompt** is rebuilt on every message by reading `soul.md` + `user.md` + `memory.md` from `MEMORY_DIR`.

**Intent detection:** every message → Haiku classifies into CAPTURE_*, TACHE, NOTION_*, or CONVERSATION. CAPTURE_* → staged in RAM + `staging.json`. TACHE → written immediately to `memory.md` fils ouverts. NOTION_* → Notion API. CONVERSATION → `ask_claude()`.

**Memory write flow (intelligent):** `/save` → `save_intelligently()` calls Sonnet with full conversation + staged captures + all memory files → returns `{ops, summary}` → shown to user as a plan → user confirms → `execute_ops()` writes all files + pushes to GitHub.

**Voice flow:** Telegram voice file → downloaded to temp `.ogg` → transcribed by Groq `whisper-large-v3` → fed into `ask_claude()` directly (bypasses intent detection).

**Startup:** `on_startup()` reloads `staging.json` and notifies the user if captures from a previous session exist.

## Memory files

| File | Purpose |
|------|---------|
| `memory/soul.md` | Companion personality and behavioral rules |
| `memory/user.md` | User profile (cognitive style, projects, context) |
| `memory/memory.md` | Persistent memory: active projects, decisions, fils ouverts |
| `memory/staging.json` | Staged captures persisted between restarts |
| `memory/projets/<slug>.md` | One file per project |
| `memory/concepts/<slug>.md` | One file per concept |
| `memory/perso/<slug>.md` | Structured personal info |
| `memory/logs/` | Raw session transcripts (auto-generated, not read by bot) |

## Telegram commands

| Command | Behavior |
|---------|----------|
| `/save` | Intelligent analysis → show write plan → user confirms → execute |
| `/reset` | Clear conversation and session log (staged captures preserved) |
| `/status` | Show exchanges count + staged captures count |
| `/update <text>` | Propose a patch to user.md with confirmation |

## Key model references

- Conversation: `claude-sonnet-4-5`
- Memory save (intelligent): `claude-sonnet-4-5`
- Intent classification: `claude-haiku-4-5-20251001`
- Voice transcription: `whisper-large-v3` via Groq

## Known bugs (to fix)

- **P1** Notion database read returns empty content (need `/v1/databases/{id}/query`)
- **P1** Notion append on database adds text blocks, not rows (need `parent.database_id`)
- **P1** `classify_intent` max_tokens=100 too low for long content → truncated JSON → CONVERSATION fallback
- **P1** `save_intelligently` max_tokens=2000 may truncate ops JSON on large sessions
- **P2** `execute_ops` uses `Path(".")` ignoring `MEMORY_DIR` env var
- **P2** `replace_section` header mismatch silently creates duplicate sections
- **P2** `NOTION_CREATE` page title is kebab-case slug instead of human-readable
- **P2** Voice messages bypass intent detection (never staged)
