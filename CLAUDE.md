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

## Architecture

`companion.py` is the single entry point. Three dicts hold in-process state:
- `conversations` — per-user message history sent to Claude on every turn
- `pending_memory` — extracted memory waiting for user validation
- `session_logs` — raw transcript of the current session

**System prompt** is rebuilt on every message by reading `soul.md` + `user.md` + `memory.md` from `MEMORY_DIR`.

**Memory write flow:** `/save` → `extract_memory()` calls Claude to summarize the session → shown to user via inline keyboard → user confirms/edits → `append_to_memory()` appends to `memory.md` + `save_raw_log()` writes full transcript to `memory/logs/`.

**Voice flow:** Telegram voice file → downloaded to temp `.ogg` → transcribed by Groq `whisper-large-v3` → fed into `ask_claude()` like text.

## Memory files

| File | Purpose |
|------|---------|
| `memory/soul.md` | Companion personality and behavioral rules |
| `memory/user.md` | User profile (cognitive style, projects, context) |
| `memory/memory.md` | Persistent memory: active projects, decisions, session log |
| `memory/logs/` | Raw session transcripts (auto-generated, not read by bot) |

## Telegram commands

| Command | Behavior |
|---------|----------|
| `/save` | Extract session memory → prompt user to validate before writing |
| `/reset` | Clear conversation and session log without saving |
| `/status` | Show number of exchanges in current session |

## Key model references

- Conversation + memory extraction: `claude-sonnet-4-5`
- Voice transcription: `whisper-large-v3` via Groq
