#!/usr/bin/env python3
"""
Research Agent — enrichit automatiquement memory/concepts/ via NotebookLM.
Cron : 0 21 * * * cd /home/rayan/code/RayanAnser/second_brain && python research_agent.py >> memory/logs/research_agent.log 2>&1
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

import anthropic

from research_pipeline import run_research

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
STAGING_FILE   = MEMORY_DIR / "staging.json"
CONCEPTS_DIR   = MEMORY_DIR / "concepts"

MAX_NOTEBOOKS_PER_RUN = 3

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

_TOPICS_SYSTEM = """\
Tu analyses les notes d'un utilisateur et identifies les sujets qui méritent une recherche approfondie.

Retourne UNIQUEMENT du JSON valide (sans markdown autour) :
{"topics": [{"slug": "kebab-case", "query": "requête de recherche précise en français"}, ...]}

Règles :
- Maximum {max} topics
- Ne propose QUE des sujets absents de la liste des concepts existants
- Privilégie les sujets mentionnés plusieurs fois ou marqués comme importants/à creuser
- slug : kebab-case, max 40 chars
- query : requête factuelle et précise, en français, adaptée à une recherche web
- Si aucun sujet pertinent : {"topics": []}
"""


def _load_existing_concepts() -> list[str]:
    if not CONCEPTS_DIR.exists():
        return []
    return [f.stem for f in sorted(CONCEPTS_DIR.glob("*.md"))]


def _load_recent_captures() -> str:
    if not STAGING_FILE.exists():
        return ""
    try:
        data = json.loads(STAGING_FILE.read_text())
        lines = []
        for captures in data.values():
            for c in captures:
                lines.append(f"[{c.get('intent', '?')}] {c.get('content', '')}")
        return "\n".join(lines)
    except Exception:
        return ""


def _identify_topics(memory_content: str, captures: str, existing: list[str]) -> list[dict]:
    existing_block = ", ".join(existing) if existing else "aucun"
    system = _TOPICS_SYSTEM.replace("{max}", str(MAX_NOTEBOOKS_PER_RUN))
    user_content = (
        f"Concepts déjà couverts (à ignorer) : {existing_block}\n\n"
        f"--- memory.md ---\n{memory_content}\n\n"
        f"--- Captures récentes ---\n{captures or 'Aucune'}"
    )
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw).get("topics", [])
    except Exception as e:
        log.error(f"_identify_topics: JSON invalide — {e}\n{raw}")
        return []


def _send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    resp.raise_for_status()


async def main_async():
    if not MEMORY_MD.exists():
        log.error(f"memory.md introuvable : {MEMORY_MD}")
        sys.exit(1)

    memory_content = MEMORY_MD.read_text()
    captures = _load_recent_captures()
    existing = _load_existing_concepts()

    log.info(f"Concepts existants : {existing}")

    topics = _identify_topics(memory_content, captures, existing)
    if not topics:
        log.info("Aucun sujet à enrichir, arrêt.")
        return

    log.info(f"{len(topics)} sujet(s) identifié(s) : {[t['slug'] for t in topics]}")

    done: list[str] = []
    failed: list[str] = []

    for topic in topics[:MAX_NOTEBOOKS_PER_RUN]:
        slug  = topic.get("slug", "")
        query = topic.get("query", "")
        if not slug or not query:
            log.warning(f"Topic invalide ignoré : {topic}")
            continue
        try:
            log.info(f"Traitement de {slug!r}…")
            result = await run_research(slug, query, MEMORY_DIR, claude)
            log.info(f"{slug} : notebook {result.notebook_url}")
            done.append(slug)
            log.info(f"{slug} : OK")
        except Exception as e:
            log.error(f"{slug} : ERREUR — {e}")
            failed.append(slug)

    if done:
        ts = datetime.now().strftime("%d/%m à %Hh")
        concepts_list = "\n".join(f"• <code>{s}</code>" for s in done)
        msg = f"📚 <b>Research Agent — {ts}</b>\n\n{concepts_list}"
        if failed:
            msg += f"\n\n⚠️ Échecs : {', '.join(failed)}"
        _send_telegram(msg)
        log.info(f"Digest envoyé. done={done} failed={failed}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
