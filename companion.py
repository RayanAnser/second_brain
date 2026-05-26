#!/usr/bin/env python3
"""
Compagnon IA Personnel — Sprint 2
Ajout : extraction mémoire automatique + validation + écriture dans memory.md
"""

import asyncio
import base64
import hashlib
import html
import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

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

from research_pipeline import run_research

try:
    from rag import init_rag, get_rag, format_search_results, _embed as rag_embed
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

try:
    from aiohttp import web as aiohttp_web
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


def md_to_html(text: str) -> str:
    """Convert Claude's Markdown output to Telegram HTML."""
    # Escape HTML chars first, then re-add our own tags
    text = html.escape(text, quote=False)
    # Fenced code blocks (before inline code)
    text = re.sub(
        r'```(?:\w+)?\n(.*?)```',
        lambda m: f'<pre>{m.group(1)}</pre>',
        text, flags=re.DOTALL
    )
    # Inline code
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    # Headers → bold (before italic to avoid * conflict)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    # Italic *text* (not touching ** already converted)
    text = re.sub(r'(?<!\*)\*(?!\*)([^\n*]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Italic _text_ (word boundaries to avoid snake_case breakage)
    text = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'<i>\1</i>', text)
    return text


# ── Config ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
GROQ_KEY        = os.environ["GROQ_API_KEY"]
CHAT_ID         = os.environ["TELEGRAM_CHAT_ID"]
if not CHAT_ID or int(CHAT_ID) == 0:
    raise ValueError("TELEGRAM_CHAT_ID doit être non-nul — vérifier le .env")
# Signal pour heartbeat.py cron : si le companion tourne, le cron s'auto-désactive.
os.environ["COMPANION_RUNNING"] = "1"
MEMORY_DIR      = Path(os.environ.get("MEMORY_DIR", "./memory"))
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO     = os.environ.get("GITHUB_REPO")   # "owner/repo"
GITHUB_BRANCH   = os.environ.get("GITHUB_BRANCH", "main")
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN")
NOTION_PARENT_PAGE_ID = os.environ.get("NOTION_PARENT_PAGE_ID")

USER_MD         = MEMORY_DIR / "user.md"
SOUL_MD         = MEMORY_DIR / "soul.md"
MEMORY_MD       = MEMORY_DIR / "memory.md"
LOGS_DIR        = MEMORY_DIR / "logs"
PROJETS_DIR     = MEMORY_DIR / "projets"
CONCEPTS_DIR    = MEMORY_DIR / "concepts"
PERSO_DIR       = MEMORY_DIR / "perso"
STAGING_FILE       = MEMORY_DIR / "staging.json"
COMMANDS_MD        = MEMORY_DIR / "COMMANDS.md"
AGENDA_MD          = MEMORY_DIR / "agenda.md"
CONSOLIDATION_FILE  = MEMORY_DIR / "last_consolidation.json"
RAG_DB              = MEMORY_DIR / "embeddings" / "index.db"
MEMORY_ARCHIVE_MD   = MEMORY_DIR / "memory_archive.md"
MEMORY_ACTIVE_MAX   = 6000

# ── Clients ──────────────────────────────────────────────────────────────────
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
groq   = Groq(api_key=GROQ_KEY)

# ── State ────────────────────────────────────────────────────────────────────
conversations:       dict[int, list] = {}  # historique par user
pending_save_ops:    dict[int, dict] = {}  # résultat save_intelligently en attente de confirmation
pending_user_update: dict[int, str]  = {}  # patch user.md en attente de validation (/update)
staged_captures:     dict[int, list] = {}  # captures stagées en attente de /save
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

_context_cache: tuple[float, str] | None = None
_CONTEXT_TTL = 60.0


def _invalidate_context_cache() -> None:
    global _context_cache
    _context_cache = None


def _cached_system(text: str) -> list[dict]:
    """Wrap a system prompt string for Anthropic prompt caching."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def load_context() -> str:
    global _context_cache
    now = time.monotonic()
    if _context_cache is not None and now - _context_cache[0] < _CONTEXT_TTL:
        return _context_cache[1]
    parts = []
    for path, label in [(SOUL_MD, "SOUL"), (USER_MD, "USER"), (MEMORY_MD, "MEMORY")]:
        if path.exists():
            parts.append(f"<{label}>\n{path.read_text()}\n</{label}>")
        else:
            log.warning(f"Fichier manquant : {path}")
    result = "\n\n".join(parts)
    _context_cache = (now, result)
    return result


def build_system_prompt(extra_files: list[Path] = []) -> str:
    extra = ""
    if extra_files:
        parts = []
        for path in extra_files:
            if path.exists():
                rel = path.relative_to(MEMORY_DIR.parent)
                parts.append(f"<MEMORY_FILE path=\"{rel}\">\n{path.read_text()}\n</MEMORY_FILE>")
        if parts:
            extra = "\n\n" + "\n\n".join(parts)

    prompt = f"""Tu es le compagnon IA personnel de l'utilisateur.
Voici ton contexte complet — lis-le attentivement avant chaque réponse.

{load_context()}{extra}

---
Règles absolues :
- Réponds toujours en français
- Sois direct, dense, sans fioritures
- Ne valide pas pour faire plaisir — dis ce que tu vois
- Une question à la fois maximum
- Si l'utilisateur part dans tous les sens, nomme-le et propose un choix
- SUPPRESSION DE CAPTURE : si l'utilisateur demande de supprimer une capture stagée, réponds uniquement "Je cherche à supprimer ça." ou équivalent neutre court. Ne confirme jamais le résultat (succès ou échec) — le système s'en occupe en arrière-plan.
"""
    delete_rule = next((l for l in prompt.splitlines() if "SUPPRESSION DE CAPTURE" in l), "(règle non trouvée)")
    print(f"[build_system_prompt] règle DELETE_STAGING (texte brut envoyé à Claude) :\n{delete_rule}", flush=True)
    return prompt



def write_user_update(patch: str):
    current = USER_MD.read_text() if USER_MD.exists() else ""
    updated = current.rstrip("\n") + "\n\n" + patch + "\n"
    USER_MD.write_text(updated)
    _invalidate_context_cache()
    log.info("user.md mis à jour.")
    _push_to_github(USER_MD, updated)
    if _RAG_AVAILABLE and get_rag():
        threading.Thread(target=get_rag().index_modified, daemon=True).start()


def save_raw_log(user_id: int):
    """Sauvegarde le log brut de la session."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_path = LOGS_DIR / f"session_{today}_{user_id}.md"
    lines = session_logs.get(user_id, [])
    log_path.write_text("\n\n".join(lines))
    log.info(f"Log brut sauvegardé : {log_path}")


# ── Cost tracking ─────────────────────────────────────────────────────────────

COSTS_FILE = LOGS_DIR / "costs.jsonl"

_MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5":         (3.00,  15.00),
    "claude-haiku-4-5-20251001": (0.25,   1.25),
    "claude-haiku-4-5":          (0.25,   1.25),
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int,
                  cache_read: int = 0, cache_creation: int = 0) -> float:
    price_in, price_out = _MODEL_PRICES.get(model, (3.00, 15.00))
    return (
        input_tokens * price_in
        + output_tokens * price_out
        + cache_read * price_in * 0.1
        + cache_creation * price_in * 1.25
    ) / 1_000_000


def _log_api_call(response, function: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        usage = response.usage
        model = response.model
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": cache_read,
            "cache_creation_tokens": cache_creation,
            "cost_usd": round(
                _compute_cost(model, usage.input_tokens, usage.output_tokens,
                               cache_read, cache_creation),
                6,
            ),
            "function": function,
        }
        with COSTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"_log_api_call échoué : {e}")


# ── User profile update ──────────────────────────────────────────────────────

async def extract_user_update(request: str) -> str:
    current = USER_MD.read_text() if USER_MD.exists() else "(vide)"
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=_cached_system(
            "Tu mets à jour un profil utilisateur en markdown.\n"
            "Reçois : le contenu actuel de user.md et une demande de mise à jour.\n"
            "Retourne UNIQUEMENT le bloc markdown à ajouter à la fin de user.md.\n"
            "Pas de préambule, pas d'explication. Sois concis : une section courte ou quelques bullet points."
        ),
        messages=[{
            "role": "user",
            "content": f"user.md actuel :\n\n{current}\n\nDemande : {request}",
        }],
    )
    _log_api_call(response, "extract_user_update")
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


# ── Mémoire intelligente ─────────────────────────────────────────────────────

_SAVE_SYSTEM = """\
Tu es un système de mémoire intelligent. Tu reçois la conversation de la session, d'éventuelles captures stagées, et le contenu actuel de tous les fichiers mémoire.

Ta tâche : décider de la meilleure façon de persister les informations importantes, en consolidant plutôt qu'en ajoutant quand l'info existe déjà.

Fichiers mémoire disponibles :
- memory/user.md        : profil utilisateur (préférences, contexte de vie, style cognitif)
- memory/memory.md      : mémoire active (décisions, idées, fils ouverts, log de sessions)
- memory/projets/<slug>.md  : un fichier par projet (crée si nouveau projet substantiel)
- memory/concepts/<slug>.md : un fichier par concept important
- memory/perso/<slug>.md    : infos personnelles structurées

Retourne UNIQUEMENT ce JSON (sans backticks, sans texte autour) :
{
  "ops": [
    {
      "path": "memory/...",
      "mode": "append|replace_section|replace_file",
      "section": "## Titre" ,
      "content": "contenu markdown",
      "reason": "justification courte"
    }
  ],
  "summary": "résumé en 1-2 phrases"
}

Règles :
- Consolide si une info similaire existe déjà (préfère replace_section à append)
- replace_file uniquement pour fichiers courts < 400 mots (user.md, perso/)
- replace_section : champ "section" obligatoire, contenu = tout ce qui va SOUS le header
- Crée de nouveaux fichiers projets/concepts si le contenu est nouveau et substantiel
- N'écris que ce qui mérite d'être retenu durablement — ignore le small talk
- Si rien de notable : {"ops": [], "summary": "Rien de notable à retenir."}
- Paths relatifs depuis la racine du projet (ex: "memory/user.md")"""

_CAPTURE_INTENTS = frozenset({"CAPTURE_IDEE", "CAPTURE_PROJET", "CAPTURE_CONCEPT", "CAPTURE_PERSO"})


async def _research_task(slug: str, query: str, chat_id: int, bot):
    try:
        result = await run_research(slug, query, MEMORY_DIR, claude)
        await bot.send_message(chat_id=chat_id, text=result.summary, parse_mode="HTML")
        await bot.send_document(
            chat_id=chat_id,
            document=result.concept_file.open("rb"),
            filename=result.concept_file.name,
        )
        await bot.send_message(
            chat_id=chat_id,
            text=f"📓 Notebook complet : {result.notebook_url}",
        )
    except Exception as e:
        log.error(f"_research_task échoué ({slug}) : {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"Recherche échouée pour «{slug}» : {e}",
        )


def stage_capture(user_id: int, content: str, hint: str):
    log.info(f"[stage_capture] user_id={user_id} staged_keys={list(staged_captures.keys())}")
    entry = {
        "content": content,
        "hint": hint,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    staged_captures.setdefault(user_id, []).append(entry)
    STAGING_FILE.parent.mkdir(parents=True, exist_ok=True)
    STAGING_FILE.write_text(json.dumps(
        {str(k): v for k, v in staged_captures.items()},
        ensure_ascii=False, indent=2,
    ))
    log.info(f"Capture stagée : [{hint}] {content[:60]!r}")


def load_staging() -> bool:
    if not STAGING_FILE.exists():
        return False
    try:
        data = json.loads(STAGING_FILE.read_text())
        canonical_uid = int(CHAT_ID)
        merged: list = []
        foreign_keys: list[str] = []
        for str_uid, captures in data.items():
            if not captures:
                continue
            if int(str_uid) == canonical_uid:
                merged.extend(captures)
            else:
                log.warning(f"load_staging: bucket étranger {str_uid!r} ({len(captures)} capture(s)) → mergé dans {canonical_uid}")
                merged.extend(captures)
                foreign_keys.append(str_uid)
        if merged:
            staged_captures[canonical_uid] = merged
        if foreign_keys:
            STAGING_FILE.write_text(json.dumps(
                {str(canonical_uid): merged},
                ensure_ascii=False, indent=2,
            ))
            log.info(f"load_staging: fichier réécrit — buckets fusionnés : {foreign_keys}")
        total = len(merged)
        if total:
            log.info(f"Staging rechargé : {total} capture(s).")
        return total > 0
    except Exception as e:
        log.error(f"load_staging échoué : {e}")
        return False


def build_memory_context() -> str:
    parts = []
    for path, label in [(SOUL_MD, "memory/soul.md"), (USER_MD, "memory/user.md"), (MEMORY_MD, "memory/memory.md")]:
        parts.append(f"[{label}]\n{path.read_text() if path.exists() else '(absent)'}")
    for subdir, name in [(PROJETS_DIR, "projets"), (CONCEPTS_DIR, "concepts"), (PERSO_DIR, "perso")]:
        if not subdir.exists():
            continue
        for f in sorted(subdir.glob("*.md")):
            content = f.read_text()
            if len(content) > 3000:
                content = content[:1500] + "\n…[tronqué]"
            parts.append(f"[memory/{name}/{f.name}]\n{content}")
    return "\n\n---\n\n".join(parts)


async def save_intelligently(user_id: int) -> dict:
    conversation_text = "\n".join(
        f"{m['role'].upper()} : {m['content']}"
        for m in conversations.get(user_id, [])
    )
    staged = staged_captures.get(user_id, [])
    staged_text = ""
    if staged:
        lines = [f"- [{e['hint']}] {e['content']} ({e['timestamp']})" for e in staged]
        staged_text = "Captures stagées :\n" + "\n".join(lines)

    user_content = f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    if conversation_text:
        user_content += f"Conversation :\n{conversation_text}\n\n"
    if staged_text:
        user_content += staged_text + "\n\n"
    user_content += f"État actuel des fichiers mémoire :\n\n{build_memory_context()}"

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        system=_cached_system(_SAVE_SYSTEM),
        messages=[{"role": "user", "content": user_content}],
    )
    _log_api_call(response, "save_intelligently")
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def execute_ops(ops: list) -> list[str]:
    _invalidate_context_cache()
    modified = []
    base = MEMORY_DIR.resolve().parent
    for op in ops:
        try:
            path    = base / op["path"]
            mode    = op["mode"]
            content = op.get("content", "")
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text() if path.exists() else ""

            if mode == "append":
                sep     = "\n\n" if existing else ""
                updated = existing.rstrip("\n") + sep + content.rstrip("\n") + "\n"

            elif mode == "replace_section":
                header = op.get("section", "").strip()
                if header and header in existing:
                    idx            = existing.index(header)
                    end_of_line    = existing.find("\n", idx) + 1
                    next_sec       = existing.find("\n##", end_of_line)
                    tail           = existing[next_sec:] if next_sec != -1 else ""
                    updated        = existing[:end_of_line] + content.rstrip("\n") + "\n" + tail
                else:
                    sep     = "\n\n" if existing else ""
                    updated = existing.rstrip("\n") + sep + (header + "\n" if header else "") + content.rstrip("\n") + "\n"

            elif mode == "replace_file":
                updated = content.rstrip("\n") + "\n"

            else:
                log.warning(f"execute_ops : mode inconnu '{mode}', ignoré.")
                continue

            path.write_text(updated)
            _push_to_github(path, updated)
            modified.append(op["path"])
            log.info(f"execute_ops : {op['path']} [{mode}] — {op.get('reason', '')}")
        except Exception as e:
            log.error(f"execute_ops : échec sur {op.get('path')} — {e}")

    _archive_overflow()
    return modified


def _archive_overflow() -> None:
    if not MEMORY_MD.exists():
        return
    content = MEMORY_MD.read_text()
    if len(content) <= MEMORY_ACTIVE_MAX:
        return

    paragraphs = content.split("\n\n")
    to_archive: list[str] = []
    remaining = paragraphs[:]

    while len("\n\n".join(remaining)) > MEMORY_ACTIVE_MAX and len(remaining) > 1:
        to_archive.append(remaining.pop(0))

    if not to_archive:
        return

    archive_existing = MEMORY_ARCHIVE_MD.read_text() if MEMORY_ARCHIVE_MD.exists() else "# Archive mémoire\n"
    archive_updated  = archive_existing.rstrip("\n") + "\n\n" + "\n\n".join(to_archive) + "\n"
    MEMORY_ARCHIVE_MD.write_text(archive_updated)
    _push_to_github(MEMORY_ARCHIVE_MD, archive_updated)

    new_memory = "\n\n".join(remaining).rstrip("\n") + "\n"
    MEMORY_MD.write_text(new_memory)
    _push_to_github(MEMORY_MD, new_memory)
    _invalidate_context_cache()
    log.info(f"_archive_overflow: archivé {len(to_archive)} bloc(s) — memory.md {len(new_memory)} chars")

    if _RAG_AVAILABLE and get_rag():
        threading.Thread(target=get_rag().index_modified, daemon=True).start()


def format_ops_plan(ops: list, summary: str) -> str:
    if not ops:
        return summary
    _MODE_LABELS = {"append": "ajout", "replace_section": "màj section", "replace_file": "réécriture"}
    lines = ["Voici ce que je propose :\n"]
    for op in ops:
        label   = _MODE_LABELS.get(op["mode"], op["mode"])
        section = f" `{op['section']}`" if op.get("section") else ""
        reason  = f" — {op['reason']}" if op.get("reason") else ""
        lines.append(f"• `{op['path']}`{section} [{label}]{reason}")
    lines.append(f"\n{summary}")
    return "\n".join(lines)


# ── Détection d'intention ─────────────────────────────────────────────────────

_INTENT_SYSTEM = """\
Classifie le message utilisateur et retourne UNIQUEMENT du JSON valide, sans texte autour.

Intentions disponibles :
- CAPTURE_IDEE      : idée, insight, réflexion à noter
- CAPTURE_PROJET    : info liée à un projet précis
- CAPTURE_CONCEPT   : définition ou explication d'un concept à retenir
- CAPTURE_PERSO     : info personnelle, contexte de vie
- TACHE             : action concrète à faire
- NOTION_READ       : lire une page Notion (slug = nom de la page)
- NOTION_APPEND     : ajouter du contenu à une page Notion existante (slug = page cible)
- NOTION_CREATE     : créer une nouvelle page Notion (slug = titre de la nouvelle page)
- RESEARCH_REQUEST  : demande de recherche approfondie sur un sujet via NotebookLM (ex: "fais une recherche sur X", "explore le sujet Y", "crée un notebook sur Z")
- AGENDA_ADD        : ajouter un rendez-vous, événement ou rappel dans l'agenda
- AGENDA_QUERY      : consulter l'agenda (aujourd'hui, cette semaine, une date précise)
- SEARCH_MEMORY     : recherche dans la mémoire personnelle (ex: "qu'est-ce que j'ai noté sur X", "cherche dans ma mémoire", "rappelle-moi ce que j'ai dit sur Y", "trouve dans mes notes")
- DELETE_STAGING    : supprimer une capture en attente (ex: "supprime la capture X", "enlève X de mes captures", "retire ça du staging")
- CONVERSATION      : tout le reste (question, discussion, conseil)

Format strict :
{"intent": "...", "slug": "...", "content": "..."}

Règles :
- slug : kebab-case pour CAPTURE_*, RESEARCH_REQUEST, SEARCH_MEMORY ; nom exact de la page pour NOTION_READ/APPEND ; titre lisible pour NOTION_CREATE ; vide "" pour TACHE/CONVERSATION/DELETE_STAGING ; date YYYY-MM-DD calculée depuis la date fournie pour AGENDA_ADD ; "aujourd'hui"/"semaine" ou YYYY-MM-DD pour AGENDA_QUERY
- content : version épurée et concise de l'info à retenir ; pour RESEARCH_REQUEST et SEARCH_MEMORY : requête de recherche reformulée en français (précise, sans la demande méta) ; vide "" pour CONVERSATION et NOTION_READ ; "HH:MM | description concise" pour AGENDA_ADD (heure au format 24h, ex: "14:00 | Dentiste — Dr. Martin") ; vide "" pour AGENDA_QUERY ; fragment de texte à chercher dans les captures pour DELETE_STAGING
- En cas de doute : CONVERSATION"""



_DAY_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


async def classify_intent(text: str) -> dict:
    now = datetime.now()
    date_ctx = f"[Aujourd'hui : {now.strftime('%Y-%m-%d')}, {_DAY_FR[now.weekday()]}]"
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=_cached_system(_INTENT_SYSTEM),
            messages=[{"role": "user", "content": f"{date_ctx}\n{text}"}],
        )
        _log_api_call(response, "classify_intent")
        raw = response.content[0].text.strip()
        log.info(f"classify_intent raw={raw!r}")
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        log.info(f"classify_intent → intent={result.get('intent')!r} slug={result.get('slug')!r}")
        return result
    except Exception as e:
        log.warning(f"classify_intent échoué ({e}), fallback CONVERSATION.")
        return {"intent": "CONVERSATION", "slug": "", "content": ""}


def _list_memory_files() -> list[tuple[str, Path]]:
    entries = []
    for subdir, name in [(PROJETS_DIR, "projets"), (CONCEPTS_DIR, "concepts"), (PERSO_DIR, "perso")]:
        if not subdir.exists():
            continue
        for f in sorted(subdir.glob("*.md")):
            entries.append((f"memory/{name}/{f.name}", f))
    return entries


async def select_memory_files(text: str) -> list[Path]:
    """Identifie les fichiers mémoire pertinents pour une question donnée."""
    available = _list_memory_files()
    if not available:
        return []

    file_list = "\n".join(f"- {label}" for label, _ in available)
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=_cached_system(
                "Tu sélectionnes les fichiers mémoire pertinents pour répondre à une question.\n"
                "Retourne UNIQUEMENT du JSON valide : {\"files\": [\"memory/...\", ...]}\n"
                "Retourne une liste vide si aucun fichier n'est pertinent.\n"
                "Ne retourne que les fichiers vraiment utiles pour répondre."
            ),
            messages=[{
                "role": "user",
                "content": f"Question : {text}\n\nFichiers disponibles :\n{file_list}",
            }],
        )
        _log_api_call(response, "select_memory_files")
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        selected = json.loads(raw).get("files", [])
        label_to_path = {label: path for label, path in available}
        result = [label_to_path[s] for s in selected if s in label_to_path]
        log.info(f"select_memory_files → {[p.name for p in result]}")
        return result
    except Exception as e:
        log.warning(f"select_memory_files échoué ({e}), extra_files=[].")
        return []


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


def _dispatch_tache(content: str):
    _append_to_section(MEMORY_MD, "Fils ouverts", content)
    _push_to_github(MEMORY_MD, MEMORY_MD.read_text())


# ── Agenda ───────────────────────────────────────────────────────────────────

def _agenda_get_entries(text: str, date: str) -> list[str]:
    header = f"## {date}"
    if header not in text:
        return []
    idx = text.index(header) + len(header)
    next_sec = text.find("\n## ", idx)
    section = text[idx:next_sec] if next_sec != -1 else text[idx:]
    return [
        line.strip()[2:]
        for line in section.splitlines()
        if line.strip().startswith("- ")
    ]


def dispatch_agenda_add(date: str, content: str) -> str:
    AGENDA_MD.parent.mkdir(parents=True, exist_ok=True)
    text = AGENDA_MD.read_text() if AGENDA_MD.exists() else ""
    header = f"## {date}"
    new_line = f"- {content}"

    if header in text:
        idx = text.index(header) + len(header)
        next_sec = text.find("\n## ", idx)
        if next_sec == -1:
            updated = text.rstrip("\n") + f"\n{new_line}\n"
        else:
            block = text[idx:next_sec].rstrip("\n")
            updated = text[:idx] + block + f"\n{new_line}" + text[next_sec:]
    else:
        pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})', re.MULTILINE)
        insert_pos = None
        for m in pattern.finditer(text):
            if m.group(1) > date:
                insert_pos = m.start()
                break
        new_section = f"## {date}\n{new_line}\n"
        if insert_pos is None:
            sep = "\n\n" if text.rstrip() else ""
            updated = text.rstrip("\n") + sep + new_section
        else:
            before = text[:insert_pos].rstrip("\n")
            updated = before + ("\n\n" if before else "") + new_section + "\n" + text[insert_pos:]

    AGENDA_MD.write_text(updated)
    _push_to_github(AGENDA_MD, updated)
    return f"📅 RDV ajouté : {content}"


def dispatch_agenda_query(slug: str) -> str:
    if not AGENDA_MD.exists():
        return "Aucun agenda pour l'instant."
    text = AGENDA_MD.read_text()
    today = datetime.now().date()

    if slug in ("aujourd'hui", "today"):
        dates = [today.strftime("%Y-%m-%d")]
    elif slug == "semaine":
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    else:
        dates = [slug]

    blocks = []
    for d in dates:
        entries = _agenda_get_entries(text, d)
        if entries:
            blocks.append(f"📅 {d}\n" + "\n".join(f"• {e}" for e in entries))

    if not blocks:
        if slug in ("aujourd'hui", "today"):
            return "Aucun RDV aujourd'hui."
        elif slug == "semaine":
            return "Aucun RDV cette semaine."
        else:
            return f"Aucun RDV le {slug}."

    return "\n\n".join(blocks)


# ── Notion ───────────────────────────────────────────────────────────────────

_NOTION_BASE        = "https://api.notion.com/v1"
_NOTION_VERSION     = "2022-06-28"
_NOTION_READ_LIMIT  = 4000


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def notion_search(query: str) -> list[dict]:
    """Retourne [{id, title}, ...] pour les pages et databases correspondant à query."""
    resp = requests.post(
        f"{_NOTION_BASE}/search",
        headers=_notion_headers(),
        json={"query": query},
        timeout=10,
    )
    resp.raise_for_status()
    results = []
    for obj in resp.json().get("results", []):
        if obj.get("object") == "database":
            # database : titre dans obj["title"] (liste de rich_text)
            rich = obj.get("title", [])
        else:
            # page : titre dans obj["properties"]["title"]["title"]
            rich = obj.get("properties", {}).get("title", {}).get("title", [])
        title = "".join(t.get("plain_text", "") for t in rich) or "(sans titre)"
        results.append({"id": obj["id"], "title": title, "type": obj.get("object", "page")})
    return results


def _blocks_to_text(blocks: list) -> str:
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        data  = block.get(btype, {})
        rich  = data.get("rich_text", [])
        text  = "".join(t.get("plain_text", "") for t in rich)
        if btype == "heading_1":
            lines.append(f"# {text}")
        elif btype == "heading_2":
            lines.append(f"## {text}")
        elif btype == "heading_3":
            lines.append(f"### {text}")
        elif btype in ("bulleted_list_item", "numbered_list_item"):
            lines.append(f"- {text}")
        elif btype == "to_do":
            checked = "x" if data.get("checked") else " "
            lines.append(f"[{checked}] {text}")
        elif text:
            lines.append(text)
    return "\n".join(lines)


def notion_get_text(page_id: str) -> str:
    resp = requests.get(
        f"{_NOTION_BASE}/blocks/{page_id}/children",
        headers=_notion_headers(),
        params={"page_size": 100},
        timeout=10,
    )
    resp.raise_for_status()
    text = _blocks_to_text(resp.json().get("results", []))
    if len(text) > _NOTION_READ_LIMIT:
        text = text[:_NOTION_READ_LIMIT] + "\n…[tronqué]"
    return text


def notion_append(page_id: str, content: str) -> None:
    lines = [l for l in content.splitlines() if l.strip()]
    if not lines:
        return
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        }
        for line in lines
    ]
    resp = requests.patch(
        f"{_NOTION_BASE}/blocks/{page_id}/children",
        headers=_notion_headers(),
        json={"children": children},
        timeout=10,
    )
    resp.raise_for_status()


def notion_create_page(title: str, content: str) -> str:
    """Crée une page sous NOTION_PARENT_PAGE_ID. Retourne l'URL."""
    lines = [l for l in content.splitlines() if l.strip()]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        }
        for line in lines
    ]
    resp = requests.post(
        f"{_NOTION_BASE}/pages",
        headers=_notion_headers(),
        json={
            "parent": {"page_id": NOTION_PARENT_PAGE_ID},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
            "children": children,
        },
        timeout=10,
    )
    resp.raise_for_status()
    page_id = resp.json()["id"]
    return f"https://notion.so/{page_id.replace('-', '')}"


def _notion_query_database(database_id: str) -> str:
    """Retourne les entrées d'une database Notion sous forme de texte."""
    resp = requests.post(
        f"{_NOTION_BASE}/databases/{database_id}/query",
        headers=_notion_headers(),
        json={"page_size": 50},
        timeout=10,
    )
    resp.raise_for_status()
    lines = []
    for page in resp.json().get("results", []):
        for prop_val in page.get("properties", {}).values():
            if prop_val.get("type") == "title":
                rich  = prop_val.get("title", [])
                title = "".join(t.get("plain_text", "") for t in rich)
                if title:
                    lines.append(f"- {title}")
                break
    text = "\n".join(lines) if lines else "(base de données vide)"
    if len(text) > _NOTION_READ_LIMIT:
        text = text[:_NOTION_READ_LIMIT] + "\n…[tronqué]"
    return text


def notion_add_database_row(database_id: str, text: str) -> None:
    """Ajoute une ligne à une database Notion."""
    resp = requests.get(
        f"{_NOTION_BASE}/databases/{database_id}",
        headers=_notion_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    title_prop = next(
        (name for name, val in resp.json().get("properties", {}).items() if val.get("type") == "title"),
        "Name",
    )
    resp = requests.post(
        f"{_NOTION_BASE}/pages",
        headers=_notion_headers(),
        json={
            "parent": {"database_id": database_id},
            "properties": {
                title_prop: {"title": [{"type": "text", "text": {"content": text}}]},
            },
        },
        timeout=10,
    )
    resp.raise_for_status()


def _notion_read_content(obj: dict) -> str:
    """Lit le contenu d'une page ou les entrées d'une database."""
    if obj["type"] == "database":
        return _notion_query_database(obj["id"])
    return notion_get_text(obj["id"])


def resolve_page(slug: str) -> dict | None:
    """Résout un nom/alias vers {id, type} Notion, ou None si introuvable."""
    pages_env = os.environ.get("NOTION_PAGES", "")
    if pages_env:
        try:
            aliases = json.loads(pages_env)
            if slug in aliases:
                entry = aliases[slug]
                # Supporte "page_id" (str) ou {"id": ..., "type": ...}
                if isinstance(entry, str):
                    return {"id": entry, "type": "page"}
                return entry
        except Exception:
            pass
    results = notion_search(slug)
    return results[0] if results else None


async def handle_notion_read(slug: str, user_message: str, user_id: int) -> str:
    if not NOTION_TOKEN:
        return "NOTION_TOKEN non configuré."
    obj = resolve_page(slug)
    if not obj:
        return f"Page Notion introuvable : « {slug} »."
    notion_content = _notion_read_content(obj)
    log.info(f"Notion content ({len(notion_content)} chars) : {notion_content[:500]}")
    # Injecté en system prompt uniquement — ne pollue pas l'historique de conversation
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=[
            {"type": "text", "text": build_system_prompt(), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"\n\n[Contenu Notion — {slug}]\n{notion_content}"},
        ],
        messages=list(conversations.get(user_id, [])) + [{"role": "user", "content": user_message}],
    )
    _log_api_call(response, "handle_notion_read")
    reply = response.content[0].text
    session_logs.setdefault(user_id, []).append(f"USER : {user_message} [lu Notion: {slug}]")
    session_logs[user_id].append(f"ASSISTANT : {reply}")
    return reply


async def handle_notion_append(slug: str, content: str) -> str:
    if not NOTION_TOKEN:
        return "NOTION_TOKEN non configuré."
    obj = resolve_page(slug)
    if not obj:
        return f"Page Notion introuvable : « {slug} »."
    if obj["type"] == "database":
        notion_add_database_row(obj["id"], content)
        return f"📝 Ligne ajoutée à la database `{slug}`."
    notion_append(obj["id"], content)
    return f"📝 Ajouté à `{slug}`."


async def handle_notion_create(slug: str, content: str) -> str:
    if not NOTION_TOKEN:
        return "NOTION_TOKEN non configuré."
    if not NOTION_PARENT_PAGE_ID:
        return "NOTION_PARENT_PAGE_ID non configuré — impossible de créer une page."
    url = notion_create_page(slug, content)
    return f"📄 Page `{slug}` créée : {url}"


# ── Transcription vocale ─────────────────────────────────────────────────────

async def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as f:
        result = groq.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            language="fr"
        )
    return result.text


# ── RAG helper ───────────────────────────────────────────────────────────────

def _build_rag_injection(query: str) -> str:
    """Lance une recherche RAG et retourne le bloc à injecter dans le message."""
    if not _RAG_AVAILABLE:
        return ""
    rag = get_rag()
    if rag is None:
        return ""
    results = rag.search(query)
    if not results:
        return ""
    formatted = format_search_results(results, MEMORY_DIR)
    return f'<MEMORY_SEARCH query="{query}">\n{formatted}\n</MEMORY_SEARCH>'


# ── HTTP companion server ─────────────────────────────────────────────────────

def _delete_staging_by_content(query: str) -> str | None:
    """Supprime la capture la plus similaire sémantiquement à `query` dans le bucket CHAT_ID.

    Seuil adaptatif : 0.35 si query <= 2 mots (vague), 0.45 si >= 3 mots (précis).
    Fallback substring si RAG indisponible.
    Retourne le contenu supprimé ou None.
    """
    uid = int(CHAT_ID)
    captures = staged_captures.get(uid, [])
    if not captures:
        return None

    n_words = len(query.split())
    threshold = 0.35 if n_words <= 2 else 0.45
    log.info(f"[delete_by_content] query={query!r} ({n_words} mot(s)) → seuil={threshold}")

    texts = [cap.get("content", "") for cap in captures]

    if _RAG_AVAILABLE:
        try:
            import numpy as np
            vecs    = rag_embed([query] + texts)   # (1 + n, dim), L2-normalisé
            q_vec   = vecs[0]
            c_vecs  = vecs[1:]
            scores  = (c_vecs @ q_vec).flatten()
            best_i  = int(np.argmax(scores))
            best_score = float(scores[best_i])
            log.info(
                f"[delete_by_content] best_score={best_score:.3f} cap={texts[best_i]!r}"
            )
            if best_score >= threshold:
                content = captures[best_i].get("content")
                captures.pop(best_i)
                if not captures:
                    staged_captures.pop(uid, None)
                STAGING_FILE.write_text(json.dumps(
                    {str(k): v for k, v in staged_captures.items()},
                    ensure_ascii=False, indent=2,
                ))
                return content
            log.info(
                f"[delete_by_content] score {best_score:.3f} < {threshold} — aucune capture supprimée"
            )
            return None
        except Exception as e:
            log.warning(f"[delete_by_content] embed échoué ({e}), fallback substring")

    # Fallback : correspondance substring simple
    query_low = query.lower()
    for i, cap in enumerate(captures):
        if query_low in cap.get("content", "").lower():
            content = cap.get("content")
            captures.pop(i)
            if not captures:
                staged_captures.pop(uid, None)
            STAGING_FILE.write_text(json.dumps(
                {str(k): v for k, v in staged_captures.items()},
                ensure_ascii=False, indent=2,
            ))
            return content
    return None


async def _http_get_staging(request):
    captures = staged_captures.get(int(CHAT_ID), [])
    result = [
        {"intent": cap.get("hint", cap.get("intent", "?")), "content": cap.get("content", "")}
        for cap in captures
    ]
    return aiohttp_web.json_response(result)


async def _http_delete_staging_by_content(request):
    try:
        data  = await request.json()
        query = str(data.get("query", "")).strip()
        if not query:
            return aiohttp_web.Response(status=400, text="query required")
        deleted = _delete_staging_by_content(query)
        if deleted:
            log.info(f"[delete_staging_by_content] supprimé : {deleted!r}")
            return aiohttp_web.json_response({"ok": True, "deleted": deleted})
        return aiohttp_web.json_response({"ok": False, "deleted": None})
    except Exception as e:
        log.error(f"HTTP /delete_staging_by_content : {e}")
        return aiohttp_web.Response(status=500, text=str(e))


async def _http_delete_staging(request):
    """Supprime la capture à l'index donné dans le bucket CHAT_ID.

    L'index correspond directement à la position dans staged_captures[CHAT_ID],
    qui est la même liste que celle renvoyée par GET /staging.
    Retourne la liste mise à jour dans {"ok": true, "captures": [...]}.
    """
    try:
        data  = await request.json()
        index = int(data.get("index", -1))
        uid   = int(CHAT_ID)

        captures = staged_captures.get(uid, [])
        if index < 0 or index >= len(captures):
            return aiohttp_web.Response(
                status=404,
                text=f"index {index} hors limites ({len(captures)} captures)",
            )

        removed = captures.pop(index)
        if not captures:
            staged_captures.pop(uid, None)

        STAGING_FILE.write_text(json.dumps(
            {str(k): v for k, v in staged_captures.items()},
            ensure_ascii=False, indent=2,
        ))
        log.info(f"[delete_staging] index={index} supprimé : {removed.get('content', '')!r}")

        current = staged_captures.get(uid, [])
        result  = [
            {"intent": c.get("hint", c.get("intent", "?")), "content": c.get("content", "")}
            for c in current
        ]
        return aiohttp_web.json_response({"ok": True, "captures": result})
    except Exception as e:
        log.error(f"HTTP /delete_staging : {e}")
        return aiohttp_web.Response(status=500, text=str(e))


async def _http_rag_search(request):
    try:
        data  = await request.json()
        query = str(data.get("query", "")).strip()
    except Exception:
        return aiohttp_web.Response(status=400, text="query required")
    if not query or not _RAG_AVAILABLE:
        return aiohttp_web.json_response({"result": ""})
    rag = get_rag()
    if rag is None:
        return aiohttp_web.json_response({"result": ""})
    try:
        results   = rag.search(query, top_k=3)
        formatted = format_search_results(results, MEMORY_DIR) if results else ""
        return aiohttp_web.json_response({"result": formatted})
    except Exception as e:
        log.error(f"HTTP /rag_search : {e}")
        return aiohttp_web.json_response({"result": ""})


async def _http_stage(request):
    try:
        data    = await request.json()
        content = str(data.get("content", "")).strip()
        hint    = str(data.get("hint", "CAPTURE_IDEE"))
        if not content:
            return aiohttp_web.Response(status=400, text="content required")
        uid = int(CHAT_ID)
        log.info(f"[_http_stage] user_id={uid} hint={hint!r} content={content[:60]!r}")
        stage_capture(uid, content, hint)
        return aiohttp_web.json_response({"ok": True})
    except Exception as e:
        log.error(f"HTTP /stage : {e}")
        return aiohttp_web.Response(status=500, text=str(e))


async def _http_task(request):
    try:
        data    = await request.json()
        content = str(data.get("content", "")).strip()
        if not content:
            return aiohttp_web.Response(status=400, text="content required")
        _dispatch_tache(content)
        return aiohttp_web.json_response({"ok": True})
    except Exception as e:
        log.error(f"HTTP /task : {e}")
        return aiohttp_web.Response(status=500, text=str(e))


# ── Claude conversation ──────────────────────────────────────────────────────

async def ask_claude(
    user_message: str,
    user_id: int,
    extra_files: list[Path] = [],
    context_injection: str = "",
) -> str:
    history = conversations.setdefault(user_id, [])

    # System prompt stable (sans extra_files) — préserve le cache prompt.
    base_system = build_system_prompt()
    sys_hash = hashlib.md5(base_system.encode()).hexdigest()[:8]
    log.info(f"ask_claude system_prompt md5={sys_hash} len={len(base_system)}")

    # Construit le contenu envoyé à l'API (extra_files + RAG injectés en préfixe).
    api_content = user_message
    if extra_files:
        parts = []
        for path in extra_files:
            if path.exists():
                rel = path.relative_to(MEMORY_DIR.parent)
                parts.append(f"<MEMORY_FILE path=\"{rel}\">\n{path.read_text()}\n</MEMORY_FILE>")
        if parts:
            api_content = "\n\n".join(parts) + "\n\n" + api_content
    if context_injection:
        log.debug(f"context_injection preview: {context_injection[:200]}")
        stripped = context_injection.lstrip()
        if stripped.startswith(("{", "[", "---\n")) or "```json" in context_injection:
            log.warning(f"context_injection contient du JSON/YAML brut — risque de polluer la réponse Claude")
        api_content = context_injection + "\n\n" + api_content

    # L'historique stocke uniquement le message brut — garde la conversation lisible
    # et le contexte injecté hors de la fenêtre multi-tour.
    history.append({"role": "user", "content": user_message})
    session_logs.setdefault(user_id, []).append(f"USER : {user_message}")

    # Pour l'appel API : historique sans le dernier tour + message enrichi
    api_messages = list(history[:-1]) + [{"role": "user", "content": api_content}]

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=_cached_system(base_system),
        messages=api_messages,
    )
    _log_api_call(response, "ask_claude")
    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    session_logs[user_id].append(f"ASSISTANT : {reply}")
    return reply


# ── Handlers Telegram ────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in pending_user_update:
        await handle_user_freetext(update, context, text)
        return

    await update.message.chat.send_action("typing")

    result  = await classify_intent(text)
    intent  = result.get("intent", "CONVERSATION")
    content = result.get("content", text)
    slug    = result.get("slug", "")

    if intent in _CAPTURE_INTENTS:
        stage_capture(user_id, content, intent)
        session_logs.setdefault(user_id, []).append(f"USER : {text}")
        session_logs[user_id].append(f"[{intent}] {content}")
        await update.message.reply_text("Noté.")
        return

    if intent == "TACHE":
        _dispatch_tache(content)
        session_logs.setdefault(user_id, []).append(f"USER : {text}")
        session_logs[user_id].append(f"[TACHE] {content}")
        await update.message.reply_text("📋 Tâche ajoutée aux fils ouverts.")
        return

    if intent == "RESEARCH_REQUEST":
        effective_slug = slug or re.sub(r"[^a-z0-9]+", "-", (content or text).lower())[:40].strip("-")
        effective_query = content or text
        asyncio.create_task(
            _research_task(effective_slug, effective_query, update.effective_chat.id, context.bot)
        )
        await update.message.reply_text(
            f"🔍 Recherche lancée sur «{effective_slug}»...\nJe t'envoie la synthèse dans quelques minutes."
        )
        return

    if intent in ("NOTION_READ", "NOTION_APPEND", "NOTION_CREATE"):
        try:
            if intent == "NOTION_READ":
                reply = await handle_notion_read(slug, text, user_id)
                await update.message.reply_text(md_to_html(reply), parse_mode="HTML")
            elif intent == "NOTION_APPEND":
                confirm = await handle_notion_append(slug, content)
                session_logs.setdefault(user_id, []).append(f"USER : {text}")
                session_logs[user_id].append(f"[NOTION_APPEND → {slug}] {content}")
                await update.message.reply_text(confirm)
            else:
                confirm = await handle_notion_create(slug, content)
                session_logs.setdefault(user_id, []).append(f"USER : {text}")
                session_logs[user_id].append(f"[NOTION_CREATE] {slug}")
                await update.message.reply_text(confirm)
        except Exception as e:
            log.error(f"Notion handler échoué ({intent}) : {e}")
            await update.message.reply_text(f"Erreur Notion : {e}")
        return

    if intent == "AGENDA_ADD":
        confirm = dispatch_agenda_add(slug, content)
        session_logs.setdefault(user_id, []).append(f"USER : {text}")
        session_logs[user_id].append(f"[AGENDA_ADD] {slug} {content}")
        await update.message.reply_text(confirm)
        return

    if intent == "AGENDA_QUERY":
        reply = dispatch_agenda_query(slug)
        await update.message.reply_text(reply)
        return

    if intent == "SEARCH_MEMORY":
        query = content or text
        injection = _build_rag_injection(query)
        reply = await ask_claude(text, user_id, context_injection=injection)
        await update.message.reply_text(md_to_html(reply), parse_mode="HTML")
        return

    if intent == "DELETE_STAGING":
        query   = content or slug or text
        deleted = _delete_staging_by_content(query)
        if deleted:
            await update.message.reply_text(f"✅ Capture supprimée : «{deleted}»")
        else:
            await update.message.reply_text(f"❌ Aucune capture trouvée pour «{query}»")
        return

    try:
        injection = _build_rag_injection(text)
        reply = await ask_claude(text, user_id, context_injection=injection)
        await update.message.reply_text(md_to_html(reply), parse_mode="HTML")
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

        result  = await classify_intent(transcript)
        intent  = result.get("intent", "CONVERSATION")
        content = result.get("content", transcript)

        if intent in _CAPTURE_INTENTS:
            stage_capture(user_id, content, intent)
            session_logs.setdefault(user_id, []).append(f"USER (vocal) : {transcript}")
            session_logs[user_id].append(f"[{intent}] {content}")
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\nNoté.", parse_mode="HTML")
        elif intent == "TACHE":
            _dispatch_tache(content)
            session_logs.setdefault(user_id, []).append(f"USER (vocal) : {transcript}")
            session_logs[user_id].append(f"[TACHE] {content}")
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n📋 Tâche ajoutée aux fils ouverts.", parse_mode="HTML")
        elif intent == "AGENDA_ADD":
            slug = result.get("slug", "")
            confirm = dispatch_agenda_add(slug, content)
            session_logs.setdefault(user_id, []).append(f"USER (vocal) : {transcript}")
            session_logs[user_id].append(f"[AGENDA_ADD] {slug} {content}")
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n{confirm}", parse_mode="HTML")
        elif intent == "AGENDA_QUERY":
            slug = result.get("slug", "aujourd'hui")
            reply = dispatch_agenda_query(slug)
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n{reply}", parse_mode="HTML")
        elif intent == "SEARCH_MEMORY":
            query = result.get("content") or transcript
            injection = _build_rag_injection(query)
            reply = await ask_claude(transcript, user_id, context_injection=injection)
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n{md_to_html(reply)}", parse_mode="HTML")
        elif intent == "DELETE_STAGING":
            query   = content or result.get("slug", "") or transcript
            deleted = _delete_staging_by_content(query)
            if deleted:
                await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n✅ Capture supprimée : «{deleted}»", parse_mode="HTML")
            else:
                await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n❌ Aucune capture trouvée pour «{query}»", parse_mode="HTML")
        else:
            injection = _build_rag_injection(transcript)
            reply = await ask_claude(transcript, user_id, context_injection=injection)
            await update.message.reply_text(f"<i>{html.escape(transcript)}</i>\n\n{md_to_html(reply)}", parse_mode="HTML")
    except Exception as e:
        log.error(f"Erreur voice : {e}")
        await update.message.reply_text("Erreur lors du traitement vocal. Réessaie.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def handle_command_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/save — analyse intelligente et demande validation avant écriture."""
    user_id = int(CHAT_ID)
    log.info(f"[handle_command_save] user_id={user_id} staged_keys={list(staged_captures.keys())}")

    if not conversations.get(user_id) and not staged_captures.get(user_id):
        await update.message.reply_text("Rien à sauvegarder.")
        return

    await update.message.chat.send_action("typing")
    await update.message.reply_text("J'analyse la session...")

    try:
        result = await save_intelligently(user_id)
    except Exception as e:
        log.error(f"save_intelligently échoué : {e}")
        await update.message.reply_text(f"Erreur lors de l'analyse : {e}")
        return

    ops     = result.get("ops", [])
    summary = result.get("summary", "")

    if not ops:
        await update.message.reply_text(f"Rien de notable à retenir.\n\n{summary}")
        return

    pending_save_ops[user_id] = result

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Exécuter", callback_data="mem_save"),
        InlineKeyboardButton("🗑 Annuler",  callback_data="mem_discard"),
    ]])

    plan = format_ops_plan(ops, summary)
    await update.message.reply_text(plan + "\n\nJe sauvegarde ?", reply_markup=keyboard)


async def handle_memory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boutons de validation mémoire."""
    query = update.callback_query
    user_id = int(CHAT_ID)
    await query.answer()

    if query.data == "mem_save":
        result = pending_save_ops.pop(user_id, None)
        if result:
            save_raw_log(user_id)
            modified = execute_ops(result.get("ops", []))
            staged_captures.pop(user_id, None)
            STAGING_FILE.write_text(json.dumps(
                {str(k): v for k, v in staged_captures.items()},
                ensure_ascii=False, indent=2,
            ))
            conversations[user_id] = []
            session_logs[user_id]  = []
            if _RAG_AVAILABLE and get_rag():
                threading.Thread(target=get_rag().index_modified, daemon=True).start()
            n = len(modified)
            await query.edit_message_text(f"✅ {n} fichier(s) mis à jour. Session réinitialisée.")
        else:
            await query.edit_message_text("Rien à sauvegarder.")

    elif query.data == "mem_discard":
        pending_save_ops.pop(user_id, None)
        await query.edit_message_text("🗑 Annulé. La session continue.")


async def handle_command_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reset — remet à zéro sans sauvegarder (captures stagées conservées)."""
    user_id = update.effective_user.id
    conversations[user_id]  = []
    session_logs[user_id]   = []
    pending_save_ops.pop(user_id, None)
    await update.message.reply_text("Session réinitialisée. Les captures stagées sont conservées.")


async def handle_command_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help — envoie le contenu de COMMANDS.md sans passer par Claude."""
    if not COMMANDS_MD.exists():
        await update.message.reply_text("Fichier d'aide introuvable (memory/commands.md).")
        return

    text = COMMANDS_MD.read_text()
    limit = 4096

    if len(text) <= limit:
        await update.message.reply_text(text)
        return

    # Découpe sur les doubles sauts de ligne pour ne pas couper en plein paragraphe
    paragraphs = text.split("\n\n")
    chunk = ""
    for para in paragraphs:
        candidate = (chunk + "\n\n" + para).lstrip("\n") if chunk else para
        if len(candidate) <= limit:
            chunk = candidate
        else:
            if chunk:
                await update.message.reply_text(chunk)
            # Paragraphe seul trop long → découpe brute à la limite
            while len(para) > limit:
                await update.message.reply_text(para[:limit])
                para = para[limit:]
            chunk = para
    if chunk:
        await update.message.reply_text(chunk)


async def handle_command_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — résumé de la session en cours."""
    user_id  = int(CHAT_ID)
    exchanges = len(conversations.get(user_id, [])) // 2
    staged    = len(staged_captures.get(user_id, []))
    lines = [f"{exchanges} échange(s) dans la session."]
    if staged:
        lines.append(f"{staged} capture(s) stagée(s) en attente.")
    if _RAG_AVAILABLE and get_rag():
        s = get_rag().stats()
        lines.append(f"RAG index : {s['chunks']} chunks / {s['files']} fichier(s).")
    lines += ["/save pour organiser et sauvegarder.", "/reset pour repartir à zéro."]
    await update.message.reply_text("\n".join(lines))


async def handle_command_costs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/costs — coûts API Anthropic par période et top fonctions."""
    if not COSTS_FILE.exists():
        await update.message.reply_text("Aucun coût enregistré pour l'instant.")
        return

    try:
        raw_lines = [l for l in COSTS_FILE.read_text().splitlines() if l.strip()]
        entries = []
        for line in raw_lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        await update.message.reply_text(f"Erreur lecture costs.jsonl : {e}")
        return

    if not entries:
        await update.message.reply_text("Aucun coût enregistré pour l'instant.")
        return

    today = datetime.now().date()

    def parse_date(ts: str):
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").date()

    today_entries = [e for e in entries if parse_date(e["timestamp"]) == today]
    week_entries  = [e for e in entries if (today - parse_date(e["timestamp"])).days < 7]
    month_entries = [e for e in entries if (today - parse_date(e["timestamp"])).days < 30]

    def fmt(lst):
        return len(lst), sum(e["cost_usd"] for e in lst)

    today_calls, today_cost = fmt(today_entries)
    week_calls,  week_cost  = fmt(week_entries)
    month_calls, month_cost = fmt(month_entries)

    fn_costs: dict[str, float] = {}
    for e in month_entries:
        fn_costs[e["function"]] = fn_costs.get(e["function"], 0.0) + e["cost_usd"]
    top3 = sorted(fn_costs.items(), key=lambda x: -x[1])[:3]

    def _cache_stats(lst):
        read_tokens = sum(e.get("cache_read_tokens", 0) for e in lst)
        creation_tokens = sum(e.get("cache_creation_tokens", 0) for e in lst)
        return read_tokens, creation_tokens

    today_cache_read, today_cache_write   = _cache_stats(today_entries)
    month_cache_read, month_cache_write   = _cache_stats(month_entries)

    def _savings(lst, read_tokens):
        """Économie vs coût sans cache : cache_read_tokens auraient coûté plein tarif."""
        total_savings = 0.0
        for e in lst:
            r = e.get("cache_read_tokens", 0)
            if not r:
                continue
            price_in, _ = _MODEL_PRICES.get(e["model"], (3.00, 15.00))
            total_savings += r * price_in * 0.9 / 1_000_000  # 90% économisé vs plein tarif
        return total_savings

    today_saved  = _savings(today_entries, today_cache_read)
    month_saved  = _savings(month_entries, month_cache_read)

    def fmt_cache(read_tok, saved):
        if not read_tok:
            return "aucun hit"
        return f"{read_tok:,} tok lus → économie ${saved:.4f}"

    out = [
        "💰 *Coûts API Anthropic*\n",
        f"*Aujourd'hui* : {today_calls} appel(s) — ${today_cost:.4f}",
        f"  Cache : {fmt_cache(today_cache_read, today_saved)}",
        f"*7 derniers jours* : {week_calls} appel(s) — ${week_cost:.4f}",
        f"*30 derniers jours* : {month_calls} appel(s) — ${month_cost:.4f}",
        f"  Cache : {fmt_cache(month_cache_read, month_saved)}",
    ]
    if top3:
        out.append("\n*Top 3 fonctions (30j)* :")
        for i, (fn, cost) in enumerate(top3, 1):
            out.append(f"{i}. `{fn}` — ${cost:.4f}")

    await update.message.reply_text("\n".join(out), parse_mode="Markdown")


async def handle_command_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search <query> — recherche sémantique dans la mémoire via RAG."""
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text(
            "Utilisation : /search <requête>\n"
            "Ex : /search projet de blog, idées sur l'IA, contact Dupont"
        )
        return

    if not _RAG_AVAILABLE:
        await update.message.reply_text("RAG non disponible (sentence-transformers manquant).")
        return

    rag = get_rag()
    if rag is None:
        await update.message.reply_text("Index RAG non initialisé.")
        return

    await update.message.chat.send_action("typing")
    results = rag.search(query)
    if not results:
        await update.message.reply_text(f"Aucun résultat pertinent pour « {query} ».")
        return

    formatted = format_search_results(results, MEMORY_DIR)
    injection  = f'<MEMORY_SEARCH query="{query}">\n{formatted}\n</MEMORY_SEARCH>'
    user_id    = update.effective_user.id
    reply      = await ask_claude(query, user_id, context_injection=injection)
    await update.message.reply_text(md_to_html(reply), parse_mode="HTML")


_DOC_SUBDIRS   = [("projets", PROJETS_DIR), ("concepts", CONCEPTS_DIR), ("perso", PERSO_DIR)]
_DOC_PAGE_SIZE = 10
_DOC_MAX       = 30  # cap for keyword search (no pagination)


def _is_active_project(path: Path) -> bool:
    try:
        content = path.read_text().lower()
        return any(kw in content for kw in ("en cours", "actif", "🟢"))
    except OSError:
        return False


# cat → (display label, directory, optional file filter)
_DOC_CATEGORIES: dict[str, tuple[str, Path, object]] = {
    "projets":  ("📁 projets",          PROJETS_DIR,  None),
    "concepts": ("🧠 concepts",         CONCEPTS_DIR, None),
    "perso":    ("👤 perso",            PERSO_DIR,    None),
    "actifs":   ("🔴 projets actifs",   PROJETS_DIR,  _is_active_project),
}


def _list_doc_files(keyword: str = "") -> list[tuple[str, Path]]:
    """All files across subdirs, optionally filtered by keyword in filename."""
    entries: list[tuple[str, Path]] = []
    for subdir, directory in _DOC_SUBDIRS:
        if not directory.exists():
            continue
        for f in sorted(directory.glob("*.md")):
            key = f"{subdir}/{f.name}"
            if not keyword or keyword.lower() in key.lower():
                entries.append((key, f))
    return entries


def _get_cat_files(cat: str) -> list[tuple[str, Path]]:
    """Files for a given category, applying its filter if any."""
    label, directory, filter_fn = _DOC_CATEGORIES[cat]
    if not directory.exists():
        return []
    subdir = "projets" if cat == "actifs" else cat  # actifs share projets/ on disk
    files = sorted(directory.glob("*.md"))
    if filter_fn:
        files = [f for f in files if filter_fn(f)]  # type: ignore[operator]
    return [(f"{subdir}/{f.name}", f) for f in files]


def _build_cat_menu() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    items = list(_DOC_CATEGORIES.items())
    for i in range(0, len(items), 2):
        row = []
        for cat, (label, _, __) in items[i:i + 2]:
            n = len(_get_cat_files(cat))
            row.append(InlineKeyboardButton(f"{label} ({n})", callback_data=f"doc_cat_{cat}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _build_file_page(
    cat: str,
    entries: list[tuple[str, Path]],
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    label = _DOC_CATEGORIES[cat][0]
    total = len(entries)
    total_pages = max(1, (total + _DOC_PAGE_SIZE - 1) // _DOC_PAGE_SIZE)
    start = page * _DOC_PAGE_SIZE
    shown = entries[start:start + _DOC_PAGE_SIZE]

    header = f"{label} — {total} fichier(s)"
    if total_pages > 1:
        header += f" (page {page + 1}/{total_pages})"

    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(shown), 2):
        row = []
        for key, path in shown[i:i + 2]:
            size_kb = path.stat().st_size / 1024
            label_btn = f"📄 {path.stem} ({size_kb:.1f} KB)"
            row.append(InlineKeyboardButton(label_btn, callback_data=f"doc_{key}"))
        rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Précédent", callback_data=f"doc_pg_{cat}_{page - 1}"))
    if start + _DOC_PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Suivant ▶", callback_data=f"doc_pg_{cat}_{page + 1}"))
    if nav:
        rows.append(nav)

    return header, InlineKeyboardMarkup(rows)


async def handle_command_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/docs → menu catégories  |  /docs <keyword> → filtre tous les fichiers."""
    keyword = " ".join(context.args).strip() if context.args else ""

    if not keyword:
        await update.message.reply_text("📂 Mes documents mémoire", reply_markup=_build_cat_menu())
        return

    entries = _list_doc_files(keyword)
    if not entries:
        await update.message.reply_text(f"Aucun fichier trouvé pour « {keyword} ».")
        return

    shown = entries[:_DOC_MAX]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(shown), 2):
        row = []
        for key, path in shown[i:i + 2]:
            size_kb = path.stat().st_size / 1024
            row.append(InlineKeyboardButton(
                f"📄 {path.stem} ({size_kb:.1f} KB)",
                callback_data=f"doc_{key}",
            ))
        rows.append(row)

    header = f"🔍 {len(shown)} fichier(s) · « {keyword} »"
    if len(entries) > _DOC_MAX:
        header += f"\n⚠️ {len(entries)} résultats, affichage limité à {_DOC_MAX}. Précise ta recherche."

    await update.message.reply_text(header, reply_markup=InlineKeyboardMarkup(rows))


async def handle_doc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data.startswith("doc_cat_"):
        cat     = data[len("doc_cat_"):]
        entries = _get_cat_files(cat)
        if not entries:
            await query.edit_message_text("Aucun fichier dans cette catégorie.")
            return
        header, markup = _build_file_page(cat, entries, 0)
        await query.edit_message_text(header, reply_markup=markup)

    elif data.startswith("doc_pg_"):
        # format: doc_pg_<cat>_<page>  — page is always last token
        rest       = data[len("doc_pg_"):]
        page_str   = rest.rsplit("_", 1)[-1]
        cat        = rest[: -(len(page_str) + 1)]
        page       = int(page_str)
        entries    = _get_cat_files(cat)
        header, markup = _build_file_page(cat, entries, page)
        await query.edit_message_text(header, reply_markup=markup)

    else:
        rel_key = data[len("doc_"):]
        path    = MEMORY_DIR / rel_key
        if not path.exists():
            await query.message.reply_text(f"Fichier introuvable : {rel_key}")
            return
        await query.message.reply_document(
            document=path.open("rb"),
            filename=path.name,
            caption=f"`{rel_key}`",
            parse_mode="Markdown",
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
        system=_cached_system(system),
        messages=[{
            "role": "user",
            "content": f"Date d'aujourd'hui : {today}\n\nmemory.md :\n\n{memory_content}",
        }],
    )
    _log_api_call(response, "_hb_analyze_memory")
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _hb_format_message(
    analysis: dict,
    freshness_days: int,
    freshness_label: str,
    today_agenda: list[str],
) -> str:
    now = datetime.now()
    date_str = f"{now.day} {_MONTHS_FR[now.month]} {now.year}"
    lines = [f"🌅 *Digest du {date_str}*"]

    if today_agenda:
        lines.append("\n📅 *Agenda du jour :*")
        for entry in today_agenda:
            lines.append(f"• {entry}")

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
        agenda_text = AGENDA_MD.read_text() if AGENDA_MD.exists() else ""
        today_agenda = _agenda_get_entries(agenda_text, today)
        message = _hb_format_message(analysis, freshness_days, freshness_label, today_agenda)
        _hb_send_telegram(message)
        log.info("Heartbeat : digest envoyé.")
        threading.Thread(target=_consolidate_archive, daemon=True, name="archive-consolidation").start()
    except Exception as e:
        log.error(f"Heartbeat : erreur — {e}")


# ── Consolidation nocturne ────────────────────────────────────────────────────

_CONSOLIDATION_SUMMARY_SYSTEM = """\
Tu résumes un log de conversation en 5 bullet points maximum.
Ne retiens que les faits mémorables : décisions, idées, infos personnelles, projets, tâches concrètes.
Ignore le small talk et les échanges sans valeur mémorielle.
Retourne UNIQUEMENT les bullet points (format "- ..."), sans préambule ni conclusion."""


def _load_consolidation_state() -> dict:
    if not CONSOLIDATION_FILE.exists():
        return {"date": "", "processed_logs": []}
    try:
        return json.loads(CONSOLIDATION_FILE.read_text())
    except Exception:
        return {"date": "", "processed_logs": []}


def _save_consolidation_state(date: str, processed_logs: list[str]) -> None:
    CONSOLIDATION_FILE.write_text(json.dumps(
        {"date": date, "processed_logs": list(processed_logs)},
        ensure_ascii=False, indent=2,
    ))


def _summarize_log_haiku(log_content: str) -> str:
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_cached_system(_CONSOLIDATION_SUMMARY_SYSTEM),
        messages=[{"role": "user", "content": log_content}],
    )
    _log_api_call(response, "_summarize_log_haiku")
    return response.content[0].text.strip()


def _consolidate_with_sonnet(summaries_text: str, staged_text: str) -> dict:
    user_content = f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    user_content += f"Résumés des sessions de la journée :\n{summaries_text}\n\n"
    if staged_text:
        user_content += staged_text + "\n\n"
    user_content += f"État actuel des fichiers mémoire :\n\n{build_memory_context()}"

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=_cached_system(_SAVE_SYSTEM),
        messages=[{"role": "user", "content": user_content}],
    )
    _log_api_call(response, "_consolidate_with_sonnet")
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _run_consolidation() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_consolidation_state()
    already_processed = set(state.get("processed_logs", []))

    if not LOGS_DIR.exists():
        log.info("Consolidation : répertoire logs absent, rien à faire.")
        _save_consolidation_state(today, list(already_processed))
        return

    all_logs = sorted(LOGS_DIR.glob("session_*.md"))
    new_logs = [f for f in all_logs if f.name not in already_processed]

    if not new_logs:
        log.info("Consolidation : aucun nouveau log.")
        _save_consolidation_state(today, list(already_processed))
        return

    log.info(f"Consolidation : {len(new_logs)} nouveau(x) log(s).")

    # Passe 1 — Haiku : résumé de chaque log non traité
    summaries = []
    for log_path in new_logs:
        try:
            content = log_path.read_text()
            if not content.strip():
                continue
            summary = _summarize_log_haiku(content)
            summaries.append(f"[{log_path.name}]\n{summary}")
            log.info(f"Consolidation : {log_path.name} résumé ({len(summary)} chars).")
        except Exception as e:
            log.error(f"Consolidation : erreur résumé {log_path.name} — {e}")

    new_processed = already_processed | {f.name for f in new_logs}

    if not summaries:
        log.info("Consolidation : tous les logs étaient vides.")
        _save_consolidation_state(today, list(new_processed))
        return

    # Captures stagées globales (tous utilisateurs)
    all_staged = [c for caps in staged_captures.values() for c in caps]
    staged_text = ""
    if all_staged:
        lines = [f"- [{e['hint']}] {e['content']} ({e['timestamp']})" for e in all_staged]
        staged_text = "Captures stagées :\n" + "\n".join(lines)

    # Passe 2 — Sonnet : consolidation intelligente
    try:
        result = _consolidate_with_sonnet("\n\n".join(summaries), staged_text)
        ops     = result.get("ops", [])
        summary = result.get("summary", "")
        if ops:
            modified = execute_ops(ops)
            log.info(f"Consolidation : {len(modified)} fichier(s) mis à jour — {summary}")
            if _RAG_AVAILABLE and get_rag():
                threading.Thread(target=get_rag().index_modified, daemon=True).start()
        else:
            log.info(f"Consolidation : rien à retenir — {summary}")
    except Exception as e:
        log.error(f"Consolidation passe 2 échouée : {e}")
        # État quand même sauvegardé pour ne pas reprocesser les logs en erreur
    finally:
        _save_consolidation_state(today, list(new_processed))
        log.info("Consolidation : état sauvegardé.")


_ARCHIVE_CONSOLIDATION_SYSTEM = """\
Tu consolides un fichier d'archive mémoire en français.
Fusionne les entrées redondantes sur un même sujet, supprime les infos obsolètes, garde les faits durables.
Conserve le format Markdown avec des sections claires.
Retourne UNIQUEMENT le contenu consolidé, sans préambule ni conclusion."""


def _consolidate_archive() -> None:
    if not MEMORY_ARCHIVE_MD.exists():
        return
    content = MEMORY_ARCHIVE_MD.read_text()
    if len(content) < 500:
        return
    try:
        response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=_ARCHIVE_CONSOLIDATION_SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        _log_api_call(response, "_consolidate_archive")
        consolidated = response.content[0].text.strip()
        MEMORY_ARCHIVE_MD.write_text(consolidated + "\n")
        _push_to_github(MEMORY_ARCHIVE_MD, consolidated + "\n")
        log.info(f"_consolidate_archive: {len(content)} → {len(consolidated)} chars")
        if _RAG_AVAILABLE and get_rag():
            threading.Thread(target=get_rag().index_modified, daemon=True).start()
    except Exception as e:
        log.error(f"_consolidate_archive: erreur — {e}")


def _heartbeat_loop():
    last_fired_date: str | None = None
    last_consolidated_date: str | None = None
    while True:
        time.sleep(60)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == 8 and last_fired_date != today:
            last_fired_date = today
            log.info("Heartbeat : déclenchement digest matinal.")
            threading.Thread(target=_run_heartbeat, daemon=True).start()
        if now.hour == 2 and last_consolidated_date != today:
            last_consolidated_date = today
            log.info("Consolidation : déclenchement nocturne.")
            threading.Thread(target=_run_consolidation, daemon=True).start()


# ── Main ─────────────────────────────────────────────────────────────────────

async def on_startup(app):
    has_staged = load_staging()
    if has_staged:
        total = sum(len(v) for v in staged_captures.values())
        try:
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"♻️ {total} capture(s) rechargée(s) depuis la session précédente. /save pour les organiser.",
            )
        except Exception as e:
            log.error(f"Notification staging au démarrage : {e}")

    if _AIOHTTP_AVAILABLE:
        _http_app = aiohttp_web.Application()
        _http_app.router.add_get ("/staging",                    _http_get_staging)
        _http_app.router.add_post("/stage",                     _http_stage)
        _http_app.router.add_post("/task",                      _http_task)
        _http_app.router.add_post("/delete_staging",            _http_delete_staging)
        _http_app.router.add_post("/delete_staging_by_content", _http_delete_staging_by_content)
        _http_app.router.add_post("/rag_search",                _http_rag_search)
        runner = aiohttp_web.AppRunner(_http_app)
        await runner.setup()
        site = aiohttp_web.TCPSite(runner, "0.0.0.0", 8765)
        await site.start()
        log.info("HTTP companion server démarré sur localhost:8765")
    else:
        log.warning("aiohttp non disponible — serveur HTTP Jarvis désactivé (pip install aiohttp)")


def main():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_ARCHIVE_MD.exists():
        MEMORY_ARCHIVE_MD.write_text("# Archive mémoire\n")
        log.info("memory_archive.md créé.")
    for path in [USER_MD, SOUL_MD, MEMORY_MD]:
        if not path.exists():
            log.warning(f"⚠️  Fichier manquant : {path}")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("help",   handle_command_help))
    app.add_handler(CommandHandler("reset",  handle_command_reset))
    app.add_handler(CommandHandler("save",   handle_command_save))
    app.add_handler(CommandHandler("status", handle_command_status))
    app.add_handler(CommandHandler("costs",  handle_command_costs))
    app.add_handler(CommandHandler("update", handle_command_update))
    app.add_handler(CommandHandler("search", handle_command_search))
    app.add_handler(CommandHandler("docs",   handle_command_docs))
    app.add_handler(CallbackQueryHandler(handle_user_callback,   pattern="^usr_"))
    app.add_handler(CallbackQueryHandler(handle_doc_callback,    pattern="^doc_"))
    app.add_handler(CallbackQueryHandler(handle_memory_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    log.info(f"GitHub sync : GITHUB_REPO={GITHUB_REPO!r} GITHUB_BRANCH={GITHUB_BRANCH!r} token={'set' if GITHUB_TOKEN else 'ABSENT'}")

    if _RAG_AVAILABLE:
        rag = init_rag(RAG_DB, MEMORY_DIR)
        log.info("RAG : index initialisé.")
        threading.Thread(target=rag.index_modified, daemon=True, name="rag-init").start()
    else:
        log.warning("RAG non disponible : pip install sentence-transformers numpy")

    threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat").start()
    log.info("Heartbeat thread démarré (digest à 8h00).")

    log.info("🤖 Compagnon IA Sprint 7 démarré.")
    app.run_polling()


if __name__ == "__main__":
    main()
