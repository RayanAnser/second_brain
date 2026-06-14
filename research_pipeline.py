#!/usr/bin/env python3
"""
Shared research pipeline: Claude web_search → NotebookLM → memory/concepts/<slug>.md

Used by both companion.py (on-demand via Telegram) and research_agent.py (cron).
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from collections.abc import Awaitable, Callable

import anthropic
from notebooklm import NotebookLMClient


@dataclass
class ResearchResult:
    summary: str       # HTML-formatted summary for Telegram
    concept_file: Path # path to memory/concepts/<slug>.md
    notebook_id: str   # NotebookLM notebook ID

    @property
    def notebook_url(self) -> str:
        return f"https://notebooklm.google.com/notebook/{self.notebook_id}"

log = logging.getLogger(__name__)

_SYNTHESIS_QUESTION = (
    "Synthétise en français les points clés, les concepts importants "
    "et les informations pratiques à retenir sur ce sujet."
)


_GeminiPostFn = Callable[[dict], Awaitable[dict]]


async def _find_urls_gemini(query: str, gemini_post_fn: _GeminiPostFn) -> list[str]:
    """URL finder using Gemini native Google Search grounding.

    Sends a generateContent request with tools=[{"google_search": {}}].
    Real URLs come from groundingMetadata.groundingChunks[].web.uri.
    Falls back to regex over the text response if grounding returns nothing.
    """
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"Trouve des sources sur : {query}"}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"maxOutputTokens": 256},
    }
    data = await gemini_post_fn(body)

    candidate = data.get("candidates", [{}])[0]
    grounding = candidate.get("groundingMetadata", {})
    chunks = grounding.get("groundingChunks", [])

    urls: list[str] = []
    for chunk in chunks:
        uri = chunk.get("web", {}).get("uri", "")
        if uri.startswith("http"):
            urls.append(uri)

    log.info(f"_find_urls_gemini: {len(chunks)} chunk(s) grounding → {len(urls)} URL(s) extraite(s)")
    for i, u in enumerate(urls):
        log.info(f"_find_urls_gemini:   [{i}] {u}")

    if not urls:
        log.warning("_find_urls_gemini: aucun groundingChunk, fallback regex sur le texte")
        text = (
            candidate.get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        urls = re.findall(r'https?://[^\s\'"<>)]+', text)

    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))][:5]  # type: ignore[func-returns-value]


def _find_urls(claude_client: anthropic.Anthropic, query: str) -> list[str]:
    """Returns up to 5 URLs via Claude web_search tool.

    URLs come from web_search_tool_result blocks, which the API populates
    before any text block — so max_tokens only limits the prose response,
    not the search results themselves.
    """
    response = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": f"Trouve les 5 meilleures sources sur : {query}"}],
    )

    log.info(f"_find_urls: stop_reason={response.stop_reason!r} nb_blocks={len(response.content)}")
    for i, block in enumerate(response.content):
        btype = getattr(block, "type", type(block).__name__)
        if btype == "text":
            log.info(f"_find_urls: block[{i}] type={btype!r} text={getattr(block, 'text', '')[:120]!r}")
        elif btype == "web_search_tool_result":
            results = getattr(block, "content", [])
            log.info(f"_find_urls: block[{i}] type={btype!r} nb_results={len(results)}")
            for j, r in enumerate(results):
                url = getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else "?")
                log.info(f"_find_urls:   result[{j}] url={url!r}")
        else:
            attrs = {a: str(getattr(block, a, ""))[:80] for a in ("name", "input", "id") if hasattr(block, a)}
            log.info(f"_find_urls: block[{i}] type={btype!r} {attrs}")

    urls: list[str] = []

    for block in response.content:
        if getattr(block, "type", "") == "web_search_tool_result":
            for result in getattr(block, "content", []):
                url = (
                    getattr(result, "url", None)
                    or (result.get("url") if isinstance(result, dict) else None)
                )
                if url and url.startswith("http"):
                    urls.append(url)

    # Fallback: regex over text blocks if the tool returned nothing
    if not urls:
        log.warning("_find_urls: aucun bloc web_search_tool_result, fallback regex")
        for block in response.content:
            if hasattr(block, "text"):
                urls.extend(re.findall(r'https?://[^\s\'"<>)]+', block.text))

    seen: set[str] = set()
    deduped = [u for u in urls if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]
    result = deduped[:5]
    log.info(f"_find_urls: {len(result)} URL(s) trouvée(s)")
    return result


def _write_concept(
    slug: str,
    urls: list[str],
    synthesis: str,
    notebook_id: str,
    memory_dir: Path,
) -> Path:
    concepts_dir = memory_dir / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    concept_file = concepts_dir / f"{slug}.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sources_block = "\n".join(f"- {url}" for url in urls)
    content = (
        f"# {slug}\n\n"
        f"_Généré le {now}_\n\n"
        f"## Sources\n\n{sources_block}\n\n"
        f"## Synthèse\n\n{synthesis}\n\n"
        f"## NotebookLM\n\n"
        f"- notebook_id: `{notebook_id}`\n"
    )
    concept_file.write_text(content)
    log.info(f"research_pipeline: concept écrit → {concept_file}")
    return concept_file


async def run_research(
    slug: str,
    query: str,
    memory_dir: Path,
    claude_client: anthropic.Anthropic | None = None,
    *,
    gemini_post_fn: _GeminiPostFn | None = None,
) -> ResearchResult:
    """Full pipeline. Returns a ResearchResult with summary, concept_file, and notebook_id.

    Exactly one of claude_client or gemini_post_fn must be provided.
    """
    if claude_client is None and gemini_post_fn is None:
        raise ValueError("Provide either claude_client or gemini_post_fn.")
    log.info(f"research_pipeline: démarrage slug={slug!r} provider={'gemini' if gemini_post_fn else 'claude'}")

    # 1. Web search → URLs
    if gemini_post_fn is not None:
        urls = await _find_urls_gemini(query, gemini_post_fn)
    else:
        urls = _find_urls(claude_client, query)  # type: ignore[arg-type]
    if not urls:
        raise RuntimeError("Aucune URL trouvée par web_search.")
    log.info(f"research_pipeline: {len(urls)} URL(s) → {urls}")

    # 2. NotebookLM
    async with await NotebookLMClient.from_storage() as client:
        notebook = await client.notebooks.create(slug)
        notebook_id = notebook.id
        log.info(f"research_pipeline: notebook créé id={notebook_id}")

        # Add sources (sequential — NotebookLM API is stateful per notebook)
        source_ids = []
        for url in urls:
            try:
                source = await client.sources.add_url(notebook_id, url)
                source_ids.append(source.id)
                log.info(f"research_pipeline: source ajoutée {url}")
            except Exception as e:
                log.warning(f"research_pipeline: source ignorée {url} — {e}")

        if not source_ids:
            raise RuntimeError("Aucune source n'a pu être ajoutée au notebook.")

        log.info(f"research_pipeline: attente indexation ({len(source_ids)} source(s))...")
        await client.sources.wait_for_sources(notebook_id, source_ids, timeout=120.0)
        log.info("research_pipeline: sources prêtes")

        result = await client.chat.ask(notebook_id, _SYNTHESIS_QUESTION)
        synthesis = result.answer
        log.info(f"research_pipeline: synthèse reçue ({len(synthesis)} chars)")

    # 3. Write memory/concepts/<slug>.md
    concept_file = _write_concept(slug, urls, synthesis, notebook_id, memory_dir)

    # 4. Build summary
    preview = synthesis[:500].rstrip()
    if len(synthesis) > 500:
        preview += "…"
    summary = (
        f"📚 <b>{slug}</b>\n\n"
        f"{preview}\n\n"
        f"<i>Sources : {len(urls)} · concept enregistré dans memory/concepts/{slug}.md</i>"
    )
    return ResearchResult(summary=summary, concept_file=concept_file, notebook_id=notebook_id)
