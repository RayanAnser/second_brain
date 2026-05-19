#!/usr/bin/env python3
"""
Compagnon IA Personnel — Sprint 1
Pipeline : Telegram → Whisper → Claude → Telegram
"""

import os
import logging
import tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import anthropic
from openai import OpenAI
from groq import Groq


# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
OPENAI_KEY       = os.environ["OPENAI_API_KEY"]       # pour Whisper

# Chemin vers tes fichiers Obsidian (adapte selon ton setup)
MEMORY_DIR       = Path(os.environ.get("MEMORY_DIR", "./memory"))
USER_MD          = MEMORY_DIR / "user.md"
SOUL_MD          = MEMORY_DIR / "soul.md"
MEMORY_MD        = MEMORY_DIR / "memory.md"

# ── Clients ──────────────────────────────────────────────────────────────────
claude  = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
# whisper = OpenAI(api_key=OPENAI_KEY)
whisper = Groq(api_key=os.environ["GROQ_API_KEY"])

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_context() -> str:
    """Charge user.md + soul.md + memory.md en un seul bloc de contexte."""
    parts = []
    for path, label in [(SOUL_MD, "SOUL"), (USER_MD, "USER"), (MEMORY_MD, "MEMORY")]:
        if path.exists():
            parts.append(f"<{label}>\n{path.read_text()}\n</{label}>")
        else:
            log.warning(f"Fichier manquant : {path}")
    return "\n\n".join(parts)


def build_system_prompt() -> str:
    context = load_context()
    return f"""Tu es le compagnon IA personnel de l'utilisateur.
Voici ton contexte complet — lis-le attentivement avant chaque réponse.

{context}

---
Règles absolues :
- Réponds toujours en français
- Sois direct, dense, sans fioritures
- Ne valide pas pour faire plaisir — dis ce que tu vois
- Une question à la fois maximum
- Si l'utilisateur part dans tous les sens, nomme-le et propose un choix
"""


async def transcribe_voice(file_path: str) -> str:
    """Transcrit un fichier audio via Whisper."""
    with open(file_path, "rb") as f:
        result = whisper.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            language="fr"
        )
    return result.text


async def ask_claude(user_message: str, conversation_history: list) -> str:
    """Envoie un message à Claude avec le contexte complet."""
    conversation_history.append({"role": "user", "content": user_message})

    response = claude.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=build_system_prompt(),
        messages=conversation_history
    )

    assistant_reply = response.content[0].text
    conversation_history.append({"role": "assistant", "content": assistant_reply})
    return assistant_reply


# ── State (conversation par user) ────────────────────────────────────────────
# Simple dict en mémoire pour Sprint 1 — persistance ajoutée en Sprint 2
conversations: dict[int, list] = {}


# ── Handlers Telegram ────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text

    if user_id not in conversations:
        conversations[user_id] = []

    await update.message.chat.send_action("typing")

    try:
        reply = await ask_claude(text, conversations[user_id])
        await update.message.reply_text(reply)
    except Exception as e:
        log.error(f"Erreur Claude : {e}")
        await update.message.reply_text("Erreur lors de la réponse. Réessaie.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in conversations:
        conversations[user_id] = []

    await update.message.chat.send_action("typing")

    # Télécharge le fichier audio
    voice_file = await update.message.voice.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await voice_file.download_to_drive(tmp_path)
        transcript = await transcribe_voice(tmp_path)
        log.info(f"Transcription : {transcript}")

        # Envoie la transcription à Claude
        reply = await ask_claude(transcript, conversations[user_id])

        # Répond avec transcription + réponse
        await update.message.reply_text(
            f"_{transcript}_\n\n{reply}",
            parse_mode="Markdown"
        )

    except Exception as e:
        log.error(f"Erreur voice : {e}")
        await update.message.reply_text("Erreur lors du traitement vocal. Réessaie.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def handle_command_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Réinitialise la conversation en cours."""
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text("Conversation réinitialisée. Nouveau contexte chargé.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Vérifie que les fichiers mémoire existent
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for path in [USER_MD, SOUL_MD, MEMORY_MD]:
        if not path.exists():
            log.warning(f"⚠️  Fichier manquant : {path} — crée-le avant de lancer.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Commandes
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("reset", handle_command_reset))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    log.info("🤖 Compagnon IA démarré. En attente de messages...")
    app.run_polling()


if __name__ == "__main__":
    main()
