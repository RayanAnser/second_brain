#!/usr/bin/env python3
"""
Compagnon IA Personnel — Sprint 2
Ajout : extraction mémoire automatique + validation + écriture dans memory.md
"""

import base64
import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

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
CHAT_ID         = os.environ["TELEGRAM_CHAT_ID"]
MEMORY_DIR      = Path(os.environ.get("MEMORY_DIR", "./memory"))
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO     = os.environ.get("GITHUB_REPO")   # "owner/repo"
GITHUB_BRANCH   = os.environ.get("GITHUB_BRANCH", "main")

USER_MD         = MEMORY_DIR / "user.md"
SOUL_MD         = MEMORY_DIR / "soul.md"
MEMORY_MD       = MEMORY_DIR / "memory.md"
LOGS_DIR        = MEMORY_DIR / "logs"
PROJETS_DIR     = MEMORY_DIR / "projets"
CONCEPTS_DIR    = MEMORY_DIR / "concepts"
PERSO_DIR       = MEMORY_DIR / "perso"

# ── Clients ──────────────────────────────────────────────────────────────────
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
groq   = Groq(api_key=GROQ_KEY)

# ── State ────────────────────────────────────────────────────────────────────
conversations:       dict[int, list] = {}  # historique par user
pending_memory:      dict[int, str]  = {}  # extraction en attente de validation
pending_user_update: dict[int, str]  = {}  # patch user.md en attente de validation
session_logs:        dict[int, list] = {}  # log brut de la session


# ── GitHub sync ──────────────────────────────────────────────────────────────

def _push_to_github(file_path: Path, content: str):
    if not GITHUB_TOKEN:
        log.warning("GitHub sync ignoré : GITHUB_TOKEN absent.")
        return
    if not GITHUB_REPO:
        log.warning("GitHub sync ignoré : GITHUB_REPO absent.")
        return
    try:
        rel = str(file_path.resolve().relative_to(Path.cwd().resolve()))
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }
        log.info(f"GitHub : GET {api_url} (branch={GITHUB_BRANCH})")
        resp = requests.get(api_url, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=10)
        log.info(f"GitHub : GET status={resp.status_code}")
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": f"bot: update {rel}",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha
        log.info(f"GitHub : PUT {api_url} sha={sha!r}")
        resp = requests.put(api_url, headers=headers, json=payload, timeout=10)
        log.info(f"GitHub : PUT status={resp.status_code} body={resp.text[:200]}")
        resp.raise_for_status()
        log.info(f"GitHub : {rel} synchronisé.")
    except Exception as e:
        log.error(f"GitHub sync échoué pour {file_path.name} : {e}")


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
    _push_to_github(MEMORY_MD, updated)


def write_user_update(patch: str):
    current = USER_MD.read_text() if USER_MD.exists() else ""
    updated = current.rstrip("\n") + "\n\n" + patch + "\n"
    USER_MD.write_text(updated)
    log.info("user.md mis à jour.")
    _push_to_github(USER_MD, updated)


def save_raw_log(user_id: int):
    """Sauvegarde le log brut de la session."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_path = LOGS_DIR / f"session_{today}_{user_id}.md"
    lines = session_logs.get(user_id, [])
    log_path.write_text("\n\n".join(lines))
    log.info(f"Log brut sauvegardé : {log_path}")


# ── User profile update ──────────────────────────────────────────────────────

async def extract_user_update(request: str) -> str:
    current = USER_MD.read_text() if USER_MD.exists() else "(vide)"
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system="""Tu mets à jour un profil utilisateur en markdown.
Reçois : le contenu actuel de user.md et une demande de mise à jour.
Retourne UNIQUEMENT le bloc markdown à ajouter à la fin de user.md.
Pas de préambule, pas d'explication. Sois concis : une section courte ou quelques bullet points.""",
        messages=[{
            "role": "user",
            "content": f"user.md actuel :\n\n{current}\n\nDemande : {request}",
        }],
    )
    return response.content[0].text.strip()


async def handle_command_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/update <demande> — propose une mise à jour de user.md avec confirmation."""
    user_id = update.effective_user.id
    request = " ".join(context.args) if context.args else ""

    if not request:
        await update.message.reply_text(
            "Dis-moi ce que tu veux ajouter à ton profil.\n"
            "Ex : /update je travaille maintenant sur le projet X"
        )
        return

    await update.message.chat.send_action("typing")
    await update.message.reply_text("Je prépare la mise à jour...")

    patch = await extract_user_update(request)
    pending_user_update[user_id] = patch

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ajouter",  callback_data="usr_save"),
            InlineKeyboardButton("🗑 Annuler", callback_data="usr_discard"),
        ],
        [InlineKeyboardButton("✏️ Modifier (réponds en texte libre)", callback_data="usr_edit")]
    ])
    await update.message.reply_text(
        f"Voici ce que je vais ajouter à ton profil :\n\n{patch}\n\nJe confirme ?",
        reply_markup=keyboard,
    )


async def handle_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boutons de validation mise à jour user.md."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "usr_save":
        patch = pending_user_update.pop(user_id, None)
        if patch:
            write_user_update(patch)
            await query.edit_message_text("✅ Profil mis à jour.")
        else:
            await query.edit_message_text("Rien à sauvegarder.")

    elif query.data == "usr_discard":
        pending_user_update.pop(user_id, None)
        await query.edit_message_text("🗑 Annulé.")

    elif query.data == "usr_edit":
        await query.edit_message_text(
            f"Patch actuel :\n\n{pending_user_update.get(user_id, '')}\n\n"
            "Envoie ta version corrigée en texte."
        )


async def handle_user_freetext(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Reçoit la version corrigée du patch user.md."""
    user_id = update.effective_user.id
    pending_user_update[user_id] = text

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ajouter",  callback_data="usr_save"),
            InlineKeyboardButton("🗑 Annuler", callback_data="usr_discard"),
        ]
    ])
    await update.message.reply_text(
        f"Version mise à jour :\n\n{text}\n\nJe confirme ?",
        reply_markup=keyboard,
    )


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


# ── Détection d'intention ─────────────────────────────────────────────────────

_INTENT_SYSTEM = """\
Classifie le message utilisateur et retourne UNIQUEMENT du JSON valide, sans texte autour.

Intentions disponibles :
- CAPTURE_IDEE    : idée, insight, réflexion à noter
- CAPTURE_PROJET  : info liée à un projet précis
- CAPTURE_CONCEPT : définition ou explication d'un concept à retenir
- CAPTURE_PERSO   : info personnelle, contexte de vie
- TACHE           : action concrète à faire
- CONVERSATION    : tout le reste (question, discussion, conseil)

Format strict :
{"intent": "...", "slug": "...", "content": "..."}

Règles :
- slug : nom en kebab-case du projet/concept/sujet perso ; vide "" pour IDEE/TACHE/CONVERSATION
- content : version épurée et concise de l'info à retenir ; vide "" pour CONVERSATION
- En cas de doute : CONVERSATION"""


async def classify_intent(text: str) -> dict:
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=_INTENT_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        return json.loads(response.content[0].text.strip())
    except Exception as e:
        log.warning(f"classify_intent échoué ({e}), fallback CONVERSATION.")
        return {"intent": "CONVERSATION", "slug": "", "content": ""}


def _append_to_section(file_path: Path, section: str, line: str):
    """Insère '- line' sous '## section', crée la section si absente."""
    content = file_path.read_text() if file_path.exists() else ""
    header = f"## {section}"
    new_line = f"- {line}"

    if header in content:
        idx = content.index(header) + len(header)
        next_sec = content.find("\n##", idx)
        if next_sec == -1:
            updated = content.rstrip("\n") + f"\n{new_line}\n"
        else:
            updated = content[:next_sec] + f"\n{new_line}" + content[next_sec:]
    else:
        updated = content.rstrip("\n") + f"\n\n{header}\n{new_line}\n"

    file_path.write_text(updated)


_CAPTURE_META = {
    "CAPTURE_IDEE":    ("💡", "Idée",    None),
    "TACHE":           ("📋", "Tâche",   None),
    "CAPTURE_PROJET":  ("📁", "Projet",  MEMORY_DIR / "projets"),
    "CAPTURE_CONCEPT": ("🧠", "Concept", MEMORY_DIR / "concepts"),
    "CAPTURE_PERSO":   ("👤", "Perso",   MEMORY_DIR / "perso"),
}


def dispatch_capture(intent: str, slug: str, content: str) -> tuple[str, Path]:
    """Écrit la capture dans le bon fichier. Retourne (confirmation, path)."""
    emoji, label, subdir = _CAPTURE_META[intent]
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    if intent == "CAPTURE_IDEE":
        _append_to_section(MEMORY_MD, "Idées en suspens", content)
        _push_to_github(MEMORY_MD, MEMORY_MD.read_text())
        return f"{emoji} Idée ajoutée dans memory.md.", MEMORY_MD

    if intent == "TACHE":
        _append_to_section(MEMORY_MD, "Fils ouverts", content)
        _push_to_github(MEMORY_MD, MEMORY_MD.read_text())
        return f"{emoji} Tâche ajoutée aux fils ouverts.", MEMORY_MD

    slug = slug or "divers"
    subdir.mkdir(parents=True, exist_ok=True)
    file_path = subdir / f"{slug}.md"
    is_new = not file_path.exists()

    if is_new:
        updated = f"# {slug}\n\n### {today}\n{content}\n"
    else:
        updated = file_path.read_text().rstrip("\n") + f"\n\n### {today}\n{content}\n"

    file_path.write_text(updated)
    _push_to_github(file_path, updated)

    verb = "créé" if is_new else "mis à jour"
    rel = file_path.relative_to(MEMORY_DIR)
    return f"{emoji} {label} `{slug}` {verb} → memory/{rel}.", file_path


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

    if user_id in pending_memory:
        await handle_memory_freetext(update, context, text)
        return

    if user_id in pending_user_update:
        await handle_user_freetext(update, context, text)
        return

    await update.message.chat.send_action("typing")

    result = await classify_intent(text)
    intent = result.get("intent", "CONVERSATION")

    if intent != "CONVERSATION":
        slug    = result.get("slug", "")
        content = result.get("content", text)
        try:
            confirm, _ = dispatch_capture(intent, slug, content)
            session_logs.setdefault(user_id, []).append(f"USER : {text}")
            session_logs[user_id].append(f"[{intent}] {content}")
            await update.message.reply_text(confirm)
        except Exception as e:
            log.error(f"dispatch_capture échoué : {e}")
            await update.message.reply_text("Erreur lors de la capture. Réessaie.")
        return

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


# ── Heartbeat matinal ────────────────────────────────────────────────────────

STALE_THREAD_DAYS = 3
STALE_MEMORY_WARN = 7

_HEARTBEAT_EXTRACT_SYSTEM = """\
Tu es un extracteur de digest matinal. Analyse le contenu de memory.md et retourne un JSON strict.

Retourne UNIQUEMENT ce JSON (aucun texte autour, aucun markdown) :
{
  "fils_ouverts_anciens": [
    {"description": "...", "date_estimee": "YYYY-MM-DD", "jours": N}
  ],
  "projet_prioritaire": {
    "nom": "...",
    "statut": "...",
    "prochaine_etape": "..."
  }
}

Règles :
- fils_ouverts_anciens : fils listés dans les sections "Fils ouverts" des sessions,
  dont la date de session est > {seuil} jours avant aujourd'hui.
  Si un fil n'a pas de date explicite, utilise la date de la session parente.
- projet_prioritaire : projet "En cours" avec le plus de blocage ou d'urgence signalée.
  Si plusieurs candidats, prends celui avec la prochaine étape la plus concrète.
- jours : nombre de jours depuis date_estimee (entier).
- Si aucun fil ancien : "fils_ouverts_anciens": []
"""

_MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _hb_check_freshness() -> tuple[int, str]:
    mtime = MEMORY_MD.stat().st_mtime
    last_modified = datetime.fromtimestamp(mtime)
    days_old = (datetime.now() - last_modified).days
    label = last_modified.strftime("%d/%m à %H:%M")
    return days_old, label


def _hb_analyze_memory(memory_content: str, today: str) -> dict:
    system = _HEARTBEAT_EXTRACT_SYSTEM.replace("{seuil}", str(STALE_THREAD_DAYS))
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Date d'aujourd'hui : {today}\n\nmemory.md :\n\n{memory_content}",
        }],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _hb_format_message(analysis: dict, freshness_days: int, freshness_label: str) -> str:
    now = datetime.now()
    date_str = f"{now.day} {_MONTHS_FR[now.month]} {now.year}"
    lines = [f"🌅 *Digest du {date_str}*"]

    if freshness_days >= STALE_MEMORY_WARN:
        lines.append(
            f"\n⚠️ _memory.md non mis à jour depuis {freshness_days} jours_"
            f" (dernière modif : {freshness_label})"
        )
    else:
        lines.append(f"\n_memory.md — dernière modif : {freshness_label}_")

    fils = analysis.get("fils_ouverts_anciens", [])
    if fils:
        lines.append(f"\n🔴 *Fils ouverts depuis +{STALE_THREAD_DAYS}j :*")
        for fil in fils:
            lines.append(f"• {fil.get('description', '')} _({fil.get('jours', '?')}j)_")
    else:
        lines.append(f"\n✅ Aucun fil ouvert depuis plus de {STALE_THREAD_DAYS} jours.")

    proj = analysis.get("projet_prioritaire", {})
    nom = proj.get("nom", "")
    if nom:
        lines.append(f"\n⭐ *Projet prioritaire : {nom}*")
        if proj.get("statut"):
            lines.append(f"Statut : {proj['statut']}")
        if proj.get("prochaine_etape"):
            lines.append(f"→ {proj['prochaine_etape']}")

    return "\n".join(lines)


def _hb_send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    resp.raise_for_status()


def _run_heartbeat():
    if not MEMORY_MD.exists():
        log.warning("Heartbeat : memory.md introuvable, digest ignoré.")
        return
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        freshness_days, freshness_label = _hb_check_freshness()
        memory_content = MEMORY_MD.read_text()
        analysis = _hb_analyze_memory(memory_content, today)
        message = _hb_format_message(analysis, freshness_days, freshness_label)
        _hb_send_telegram(message)
        log.info("Heartbeat : digest envoyé.")
    except Exception as e:
        log.error(f"Heartbeat : erreur — {e}")


def _heartbeat_loop():
    last_fired_date: str | None = None
    while True:
        time.sleep(60)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == 8 and last_fired_date != today:
            last_fired_date = today
            log.info("Heartbeat : déclenchement digest matinal.")
            threading.Thread(target=_run_heartbeat, daemon=True).start()


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
    app.add_handler(CommandHandler("update", handle_command_update))
    app.add_handler(CallbackQueryHandler(handle_user_callback,   pattern="^usr_"))
    app.add_handler(CallbackQueryHandler(handle_memory_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    log.info(f"GitHub sync : GITHUB_REPO={GITHUB_REPO!r} GITHUB_BRANCH={GITHUB_BRANCH!r} token={'set' if GITHUB_TOKEN else 'ABSENT'}")
    threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat").start()
    log.info("Heartbeat thread démarré (digest à 8h00).")

    log.info("🤖 Compagnon IA Sprint 2 démarré.")
    app.run_polling()


if __name__ == "__main__":
    main()
