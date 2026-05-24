#!/usr/bin/env python3
"""
Heartbeat Sprint 3 — digest matinal automatique
Cron : 0 8 * * * cd /home/rayan/code/RayanAnser/second_brain && python heartbeat.py >> memory/logs/heartbeat.log 2>&1
"""

import html
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

import anthropic

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
MEMORY_DIR     = Path(os.environ.get("MEMORY_DIR", "./memory"))
MEMORY_MD      = MEMORY_DIR / "memory.md"

STALE_THREAD_DAYS = 3
STALE_MEMORY_WARN = 7  # warning si memory.md pas touché depuis N jours

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


# ── Fraîcheur ─────────────────────────────────────────────────────────────────

def check_freshness() -> tuple[int, str]:
    """Retourne (jours_depuis_modif, label_lisible)."""
    mtime = MEMORY_MD.stat().st_mtime
    last_modified = datetime.fromtimestamp(mtime)
    days_old = (datetime.now() - last_modified).days
    label = last_modified.strftime("%d/%m à %H:%M")
    return days_old, label


# ── Analyse Claude ────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = """\
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


def analyze_memory(memory_content: str, today: str) -> dict:
    system = EXTRACT_SYSTEM.replace("{seuil}", str(STALE_THREAD_DAYS))
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Date d'aujourd'hui : {today}\n\nmemory.md :\n\n{memory_content}",
        }],
    )
    raw = response.content[0].text.strip()
    # Claude enveloppe parfois le JSON dans des backticks markdown
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"JSON invalide reçu de Claude :\n{raw}")
        raise RuntimeError("Réponse Claude non parseable") from e


# ── Formatage message ─────────────────────────────────────────────────────────

MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def date_fr(dt: datetime) -> str:
    return f"{dt.day} {MONTHS_FR[dt.month]} {dt.year}"


def format_message(analysis: dict, freshness_days: int, freshness_label: str) -> str:
    now = datetime.now()
    lines = [f"🌅 <b>Digest du {date_fr(now)}</b>"]

    # Fraîcheur de memory.md
    if freshness_days >= STALE_MEMORY_WARN:
        lines.append(
            f"\n⚠️ <i>memory.md non mis à jour depuis {freshness_days} jours</i>"
            f" (dernière modif : {html.escape(freshness_label)})"
        )
    else:
        lines.append(f"\n<i>memory.md — dernière modif : {html.escape(freshness_label)}</i>")

    # Fils ouverts anciens
    fils = analysis.get("fils_ouverts_anciens", [])
    if fils:
        lines.append(f"\n🔴 <b>Fils ouverts depuis +{STALE_THREAD_DAYS}j :</b>")
        for fil in fils:
            desc  = html.escape(fil.get("description", ""))
            jours = html.escape(str(fil.get("jours", "?")))
            lines.append(f"• {desc} <i>({jours}j)</i>")
    else:
        lines.append(f"\n✅ Aucun fil ouvert depuis plus de {STALE_THREAD_DAYS} jours.")

    # Projet prioritaire
    proj = analysis.get("projet_prioritaire", {})
    nom  = proj.get("nom", "")
    if nom:
        lines.append(f"\n⭐ <b>Projet prioritaire : {html.escape(nom)}</b>")
        statut = proj.get("statut", "")
        if statut:
            lines.append(f"Statut : {html.escape(statut)}")
        next_step = proj.get("prochaine_etape", "")
        if next_step:
            lines.append(f"→ {html.escape(next_step)}")

    return "\n".join(lines)


# ── Envoi Telegram ────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    resp.raise_for_status()
    log.info(f"Message Telegram envoyé (HTTP {resp.status_code})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not MEMORY_MD.exists():
        log.error(f"memory.md introuvable : {MEMORY_MD}")
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    freshness_days, freshness_label = check_freshness()
    log.info(f"memory.md : {freshness_days}j depuis dernière modification ({freshness_label})")

    memory_content = MEMORY_MD.read_text()
    log.info("Appel Claude pour analyse...")
    analysis = analyze_memory(memory_content, today)

    fils_count = len(analysis.get("fils_ouverts_anciens", []))
    proj_nom   = analysis.get("projet_prioritaire", {}).get("nom", "?")
    log.info(f"Résultat : {fils_count} fil(s) ancien(s), projet prioritaire = {proj_nom}")

    message = format_message(analysis, freshness_days, freshness_label)
    send_telegram(message)
    log.info("Digest envoyé.")


if __name__ == "__main__":
    main()
