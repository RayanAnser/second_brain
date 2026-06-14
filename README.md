# Jarvis / Second Brain

A personal AI system built around a persistent memory layer and a low-latency voice interface. It runs as two cooperating processes: a Python backend that owns memory and handles Telegram, and a Rust/Tauri desktop overlay that handles real-time voice conversation.

The system is intentionally personal — its personality, tone, and behavioral rules are defined in a plain-text `soul.md` file, not in code.

---

## Vision

Most AI assistants start from scratch on every conversation. This one doesn't.

Every exchange is analyzed for durable facts, decisions, and open threads. Those are staged for review and — once confirmed — written into a structured memory graph of Markdown files. The next conversation begins with full context: who you are, what you're working on, what you decided last week.

The voice interface is designed for low friction. Push-to-talk, instant transcription, sentence-by-sentence TTS so the first word plays before the full response is generated. No typing required.

---

## Architecture

### Voice conversation flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Jarvis Desktop (Tauri / Rust)                                  │
│                                                                 │
│  Microphone → [Groq Whisper STT] → text                        │
│                    │                                            │
│                    ├──→ [Haiku / Gemini Flash] intent classify  │
│                    │         │                                  │
│                    │         ├── CAPTURE_* → /stage (HTTP)      │
│                    │         ├── TACHE      → /task  (HTTP)     │
│                    │         ├── AGENDA_*   → /agenda (HTTP)    │
│                    │         └── SEARCH     → RAG inject        │
│                    │                                            │
│                    └──→ [Claude Sonnet / Gemini Flash] stream   │
│                               │                                 │
│                    ┌──────────┘                                 │
│                    │  token stream                              │
│                    ↓                                            │
│           sentence splitter → [ElevenLabs TTS] → audio         │
│                    │                                            │
│                    └──→ memory extraction (Haiku, async)        │
│                               │                                 │
│                               └──→ /stage (HTTP) → staging.json│
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP (localhost:8765)
┌─────────────────────────┴───────────────────────────────────────┐
│  Companion Backend (Python / asyncio)                           │
│                                                                 │
│  aiohttp HTTP server ──→ staging / memory / agenda / RAG        │
│                                                                 │
│  Telegram bot ──→ text & voice messages                         │
│                    │                                            │
│                    ├── [Groq Whisper] voice transcription       │
│                    ├── intent classification (Haiku / Gemini)   │
│                    └── ask_claude() / ask_gemini() response     │
│                                                                 │
│  /save ──→ [Claude Sonnet] full-session analysis                │
│             └──→ structured write plan → user confirms          │
│                   └──→ write Markdown files + GitHub sync       │
│                                                                 │
│  research pipeline ──→ [Tavily Search] → [NotebookLM]          │
│                         └──→ memory/concepts/<slug>.md          │
└─────────────────────────────────────────────────────────────────┘
```

### Memory write flow

```
conversation ends
      │
      ├── auto: Haiku extracts facts → staging.json (per-turn, silent)
      │
      └── /save command:
            Claude Sonnet reads full session + all staged captures
            + all memory files → produces structured write plan
                  │
                  user reviews plan in Telegram
                  │
                  confirms → execute_ops() writes files → GitHub push
```

---

## Stack

| Layer | Technology | Version |
|---|---|---|
| Desktop shell | Tauri | 2.x |
| Desktop UI | React + TypeScript | 18 / 5.5 |
| Desktop build | Vite | 5.x |
| Desktop backend | Rust (tokio async, reqwest, serde) | 1.x |
| Companion backend | Python (asyncio, aiohttp) | 3.12+ |
| RAG embeddings | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) | local, no cost |
| RAG store | SQLite + numpy cosine similarity | — |
| STT | Groq Whisper (`whisper-large-v3-turbo`) | — |
| TTS | ElevenLabs (`eleven_v3`) | — |
| Conversation LLM | Claude Sonnet 4.5 or Gemini 3.5 Flash | switchable via `LLM_PROVIDER` |
| Classification LLM | Claude Haiku 4.5 or Gemini 3.5 Flash | matches provider |
| Memory analysis LLM | Claude Sonnet 4.5 or Gemini 3.5 Flash | — |
| Vision (screen read) | Gemini 3.5 Flash | multimodal |
| Web research | Tavily Search + NotebookLM | — |
| Mobile interface | Telegram Bot API | — |
| Memory sync | GitHub API (contents endpoint) | — |

---

## Features

### Desktop (Jarvis overlay)

- **Push-to-talk voice** — hold to speak, release to send; mic state visualized with an animated orb
- **Streaming TTS** — ElevenLabs starts speaking at the first sentence boundary, not after the full response
- **Screen read** — say "regarde mon écran" → screenshot captured, sent to Gemini Vision, answered vocally
- **Intent routing** — every utterance is silently classified; ideas, tasks, and calendar entries are captured without interrupting the conversation
- **Floating capture cards** — staged items appear as dismissible cards; confirm to write to memory, delete to discard
- **Memory browser** — sidebar to search and read `projets/`, `concepts/`, `perso/` files
- **Provider switch** — `LLM_PROVIDER=claude` or `LLM_PROVIDER=gemini` at runtime; all paths supported

### Telegram (Companion bot)

- Text and voice messages (OGG voice notes transcribed via Groq)
- Same intent classification and memory capture pipeline as the desktop
- `/save` — triggers intelligent session analysis → write plan → user confirms → files written
- `/reset` — clears conversation history (staged captures preserved)
- `/status` — current exchange count and pending capture count
- `/update <text>` — propose a patch to `user.md` with confirmation

### Research pipeline

Triggered by intent or Telegram command: Tavily fetches 5 real URLs → NotebookLM creates a notebook, indexes sources, generates a synthesis → result written to `memory/concepts/<slug>.md` → summary sent to Telegram with the concept file attached.

---

## Memory architecture

All persistent state lives under `MEMORY_DIR` (default `./memory`). Files are plain Markdown, editable by hand.

| Path | Purpose | Written by |
|---|---|---|
| `soul.md` | Companion personality, tone rules, behavioral constraints | Human |
| `user.md` | User profile: cognitive style, preferences, context | `/update`, `/save` |
| `memory.md` | Active memory: projects, decisions, open threads | `/save`, auto-capture |
| `taches.md` | Task list (open threads from `TACHE` intents) | Auto on TACHE intent |
| `agenda.md` | Calendar entries (`AGENDA_ADD` intents) | Auto on AGENDA_ADD |
| `staging.json` | Pending captures (RAM-backed, persisted for restart recovery) | Auto per turn |
| `projets/<slug>.md` | One file per tracked project | `/save` |
| `concepts/<slug>.md` | Research outputs (Tavily + NotebookLM synthesis) | Research pipeline |
| `perso/<slug>.md` | Structured personal information | `/save` |
| `embeddings/index.db` | SQLite vector store for RAG | `init_rag()` on startup |
| `logs/` | Raw session transcripts (not read by the system) | Auto per session |

**RAG injection**: before every LLM call, a cosine similarity search over the vector store retrieves the top-5 relevant chunks (threshold 0.25) and injects them as `<MEMORY_CONTEXT>` into the system prompt. The index is updated incrementally on file mtime changes.

---

## Setup

This is a personal system with several hard dependencies. A partial setup will run the Telegram bot; the full setup requires accounts with Groq, ElevenLabs, Tavily, and a Tauri build environment.

### Requirements

- Python 3.12+
- Node.js 18+ and npm (for the desktop frontend)
- Rust toolchain (for Tauri)
- Accounts: Anthropic, Groq, ElevenLabs, Tavily, Telegram BotFather

### Environment variables

```
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=

ANTHROPIC_API_KEY=
GROQ_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
TAVILY_API_KEY=

GEMINI_API_KEY=           # required if LLM_PROVIDER=gemini
LLM_PROVIDER=claude       # claude | gemini

MEMORY_DIR=./memory
COMPANION_URL=http://localhost:8765

GITHUB_TOKEN=             # optional — enables memory file sync to GitHub
GITHUB_REPO=owner/repo
GITHUB_BRANCH=main

NOTION_TOKEN=             # optional — enables Notion capture intents
NOTION_PARENT_PAGE_ID=
```

### Companion backend

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python companion.py
```

The companion starts an aiohttp server on port 8765 and a Telegram bot. Both run in the same asyncio loop.

### Desktop app

```bash
cd jarvis
npm install
npm run tauri dev      # development
npm run tauri build    # production binary
```

The desktop app reads the same `.env` file and connects to the companion over localhost. Both must be running for full functionality; the desktop has graceful fallbacks for most companion-dependent features.

### Memory initialization

```
memory/
├── soul.md       ← define the AI personality here
├── user.md       ← describe yourself
└── memory.md     ← start empty or seed with context
```

The RAG index builds automatically on first startup. Sentence-transformers downloads the embedding model (~120 MB) on first use.

---

## Project structure

```
second_brain/
├── companion.py           # Telegram bot + HTTP server + memory write logic
├── research_pipeline.py   # Tavily → NotebookLM → concepts/<slug>.md
├── rag.py                 # Local embeddings, SQLite store, cosine search
├── requirements.txt
├── memory/                # All persistent state (Markdown + JSON)
└── jarvis/                # Desktop overlay
    ├── src/               # React + TypeScript frontend
    │   ├── App.tsx
    │   ├── store.ts
    │   ├── components/    # ConversationArea, StagingPanel, OrbVisualizer, …
    │   └── hooks/         # useClaudeStream, useGeminiLive
    └── src-tauri/         # Rust backend
        └── src/commands/
            ├── claude.rs       # LLM streaming, intent classification, memory extraction
            ├── gemini_live.rs  # Groq STT
            ├── gemini_tts.rs   # ElevenLabs TTS
            ├── screen.rs       # Screenshot capture + Gemini Vision
            ├── memory.rs       # Memory file I/O, staging CRUD
            └── widgets.rs      # Context widget data
```
