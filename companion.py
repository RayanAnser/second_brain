#!/usr/bin/env python3
"""
Compagnon IA Personnel — Sprint 2
Ajout : extraction mémoire automatique + validation + écriture dans memory.md
"""

import os
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)
import anthropic
from groq import Groq

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
GROQ_KEY        = os.environ["GROQ_API_KEY"]
MEMORY_DIR      = Path(os.environ.get("MEMORY_DIR", "./memory"))

USER_MD         = MEMORY_DIR / "user.md"
SOUL_MD         = MEMORY_DIR / "soul.md"
MEMORY_MD       = MEMORY_DIR / "memory.md"
LOGS_DIR        = MEMORY_DIR / "logs"

# ── Clients ──────────────────────────────────────────────────────────────────
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
groq   = Groq(api_key=GROQ_KEY)

# ── State ────────────────────────────────────────────────────────────────────
conversations:  dict[int, list] = {}  # historique par user
pending_memory: dict[int, str]  = {}  # extraction en attente de validation
session_logs:   dict[int, list] = {}  # log brut de la session


# ── Helpers fichiers ─────────────────────────────────────────────────────────

def load_context() -> str:
    parts = []
    for path, label in [(SOUL_MD, "SOUL"), (USER_MD, "USER"), (MEMORY_MD, "MEMORY")]:
        if path.exists():
            parts.append(f"<{label}>\n{path.read_text()}\n</{label}>")
        else:
            log.warning(f"Fichier manquant : {path}")
    return "\n\n".join(parts)


def build_system_prompt() -> str:
    return f"""Tu es le compagnon IA personnel de l'utilisateur.
Voici ton contexte complet — lis-le attentivement avant chaque réponse.

{load_context()}

---
Règles absolues :
- Réponds toujours en français
- Sois direct, dense, sans fioritures
- Ne valide pas pour faire plaisir — dis ce que tu vois
- Une question à la fois maximum
- Si l'utilisateur part dans tous les sens, nomme-le et propose un choix
"""


def append_to_memory(extracted: str):
    """Ajoute l'extraction validée dans memory.md."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    memory_content = MEMORY_MD.read_text() if MEMORY_MD.exists() else ""

    log_section = "## 📋 Log des sessions"
    new_entry = f"\n### Session — {today}\n{extracted}\n"

    if log_section in memory_content:
        updated = memory_content.replace(log_section, log_section + new_entry)
    else:
        updated = memory_content + f"\n\n{log_section}\n{new_entry}"

    MEMORY_MD.write_text(updated)
    log.info("memory.md mis à jour.")


def save_raw_log(user_id: int):
    """Sauvegarde le log brut de la session."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_path = LOGS_DIR / f"session_{today}_{user_id}.md"
    lines = session_logs.get(user_id, [])
    log_path.write_text("\n\n".join(lines))
    log.info(f"Log brut sauvegardé : {log_path}")


# ── Extraction mémoire ───────────────────────────────────────────────────────

async def extract_memory(user_id: int) -> str:
    """Demande à Claude d'extraire ce qui mérite d'être mémorisé."""
    history = conversations.get(user_id, [])
    if not history:
        return "RIEN_A_RETENIR"

    conversation_text = "\n".join([
        f"{m['role'].upper()} : {m['content']}"
        for m in history
    ])

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system="""Tu es un extracteur de mémoire. Ton job : lire une conversation et extraire UNIQUEMENT ce qui mérite d'être retenu durablement.

Format de sortie strict (markdown) :
**Décisions prises :** (si aucune, omets la section)
- ...

**Idées capturées :** (si aucune, omets la section)
- ...

**Projets mis à jour :** (si aucun, omets la section)
- Nom du projet → nouvelle info

**Fils ouverts :** (questions non résolues, sujets à reprendre)
- ...

Règles :
- Sois concis — une ligne par élément
- N'invente rien qui n'est pas dans la conversation
- Si rien de notable, réponds uniquement : RIEN_A_RETENIR""",
        messages=[{"role": "user", "content": f"Conversation :\n\n{conversation_text}"}]
    )

    return response.content[0].text.strip()


# ── Transcription vocale ─────────────────────────────────────────────────────

async def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as f:
        result = groq.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            language="fr"
        )
    return result.text


# ── Claude conversation ──────────────────────────────────────────────────────

async def ask_claude(user_message: str, user_id: int) -> str:
    history = conversations.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})
    session_logs.setdefault(user_id, []).append(f"USER : {user_message}")

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=build_system_prompt(),
        messages=history
    )

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    session_logs[user_id].append(f"ASSISTANT : {reply}")
    return reply


# ── Handlers Telegram ────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Si une validation est en attente, traite comme correction
    if user_id in pending_memory:
        await handle_memory_freetext(update, context, text)
        return

    await update.message.chat.send_action("typing")
    try:
        reply = await ask_claude(text, user_id)
        await update.message.reply_text(reply)
    except Exception as e:
        log.error(f"Erreur Claude : {e}")
        await update.message.reply_text("Erreur. Réessaie.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")

    voice_file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await voice_file.download_to_drive(tmp_path)
        transcript = await transcribe_voice(tmp_path)
        log.info(f"Transcription : {transcript}")

        reply = await ask_claude(transcript, user_id)
        await update.message.reply_text(
            f"_{transcript}_\n\n{reply}",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"Erreur voice : {e}")
        await update.message.reply_text("Erreur lors du traitement vocal. Réessaie.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def handle_command_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/save — extrait la mémoire de la session et demande validation."""
    user_id = update.effective_user.id

    if not conversations.get(user_id):
        await update.message.reply_text("Pas de conversation à sauvegarder.")
        return

    await update.message.chat.send_action("typing")
    await update.message.reply_text("J'analyse la session...")

    extracted = await extract_memory(user_id)

    if extracted == "RIEN_A_RETENIR":
        await update.message.reply_text("Rien de notable à retenir dans cette session.")
        return

    pending_memory[user_id] = extracted

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sauvegarder", callback_data="mem_save"),
            InlineKeyboardButton("🗑 Ignorer",     callback_data="mem_discard"),
        ],
        [InlineKeyboardButton("✏️ Modifier (réponds en texte libre)", callback_data="mem_edit")]
    ])

    await update.message.reply_text(
        f"Voici ce que je retiens de cette session :\n\n{extracted}\n\n"
        "Je sauvegarde dans ta mémoire ?",
        reply_markup=keyboard
    )


async def handle_memory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boutons de validation mémoire."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "mem_save":
        extracted = pending_memory.pop(user_id, None)
        if extracted:
            save_raw_log(user_id)
            append_to_memory(extracted)
            conversations[user_id] = []
            session_logs[user_id] = []
            await query.edit_message_text("✅ Sauvegardé dans ta mémoire. Session réinitialisée.")
        else:
            await query.edit_message_text("Rien à sauvegarder.")

    elif query.data == "mem_discard":
        pending_memory.pop(user_id, None)
        await query.edit_message_text("🗑 Ignoré. La session continue.")

    elif query.data == "mem_edit":
        await query.edit_message_text(
            f"Extraction actuelle :\n\n{pending_memory.get(user_id, '')}\n\n"
            "Envoie ta version corrigée en texte."
        )


async def handle_memory_freetext(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Reçoit la version corrigée de l'extraction."""
    user_id = update.effective_user.id
    pending_memory[user_id] = text

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sauvegarder", callback_data="mem_save"),
            InlineKeyboardButton("🗑 Ignorer",     callback_data="mem_discard"),
        ]
    ])
    await update.message.reply_text(
        f"Version mise à jour :\n\n{text}\n\nJe sauvegarde ?",
        reply_markup=keyboard
    )


async def handle_command_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reset — remet à zéro sans sauvegarder."""
    user_id = update.effective_user.id
    conversations[user_id] = []
    pending_memory.pop(user_id, None)
    session_logs[user_id] = []
    await update.message.reply_text("Session réinitialisée.")


async def handle_command_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — résumé de la session en cours."""
    user_id = update.effective_user.id
    count = len(conversations.get(user_id, [])) // 2
    await update.message.reply_text(
        f"{count} échange(s) dans la session.\n"
        "/save pour extraire et sauvegarder.\n"
        "/reset pour repartir à zéro."
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for path in [USER_MD, SOUL_MD, MEMORY_MD]:
        if not path.exists():
            log.warning(f"⚠️  Fichier manquant : {path}")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("reset",  handle_command_reset))
    app.add_handler(CommandHandler("save",   handle_command_save))
    app.add_handler(CommandHandler("status", handle_command_status))
    app.add_handler(CallbackQueryHandler(handle_memory_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    log.info("🤖 Compagnon IA Sprint 2 démarré.")
    app.run_polling()


if __name__ == "__main__":
    main()
