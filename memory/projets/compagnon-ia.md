# Compagnon IA personnel (Jarvis)

**Statut** : MVP à ~98% — phase de test en conditions réelles

**Vision** : Compagnon IA personnel toujours disponible sur le bureau, qui connaît Rayan, capture ses pensées, l'aide à se structurer et évolue avec lui.

---

## Stack technique

| Composant | Technologie |
|---|---|
| STT | Groq Whisper large-v3-turbo (~250ms) |
| LLM | Gemini 3.5 Flash (fallback depuis Claude épuisé) |
| TTS | ElevenLabs eleven_v3, voix F1toM6PcP54s45kOOAyV |
| Mémoire | companion.py + RAG SQLite OpenAI embeddings |
| Desktop | Tauri 2 + React + Three.js |
| Déploiement | Railway (companion) + Windows local (Jarvis) |

---

## Architecture mémoire

| Fichier | Rôle | Injecté prompt | RAG |
|---|---|---|---|
| soul.md | Personnalité Jarvis | ✅ | ✅ |
| user.md | Profil cognitif/pro | ✅ | ✅ |
| memory.md | Contexte récent, décisions | ✅ | ✅ |
| jarvis_style.md | Corpus ton TARS/JARVIS | ✅ | ✅ |
| profil-personnel.md | Famille, amis, relations | ❌ | ✅ |
| taches.md | Todo list | ❌ | ✅ |
| agenda.md | Événements datés | ❌ | ✅ |
| memory_archive.md | Débordement memory.md | ❌ | ✅ |
| idees/*.md | Un fichier par idée, enrichissement RAG | ❌ | ✅ |
| embeddings/index.db | RAG SQLite | — | — |

---

## Fonctionnalités opérationnelles

### Pipeline vocal desktop
- Push-to-talk Ctrl+Space ou Ctrl+0
- STT Groq Whisper → LLM Gemini 3.5 Flash → TTS ElevenLabs v3
- Streaming tokens → détection fin de phrase → TTS semi-parallèle (max 2 requêtes simultanées)
- Vision écran : "regarde mon écran" → screenshot → Gemini Vision → réponse vocale

### UI Desktop (Tauri 2 + React)
- Mode compact : orbe flottante 200×200 transparente sur le bureau, always-on-top, autostart Windows
- Mode étendu : double clic → UI complète avec widgets contextuels
- Widgets : agenda (événements futurs), projets actifs, fils ouverts, tâches en cours
- Cartes staging : captures validables (👍/👎 feedback, → ok, → mem, ✕)
- Orbe Three.js constellation : 4 états idle/listening/thinking/speaking, pulse audio

### Capture et classification
- Classify intent (Gemini, json_mode, max_tokens 2048) : CAPTURE_IDEE, TACHE, CAPTURE_PERSO, AGENDA_ADD, AGENDA_QUERY, DELETE_STAGING, SEARCH_MEMORY, SCREEN_READ, CONVERSATION
- Extract memory auto post-turn : Gemini extrait les faits durables → stagés comme MEMORY
- Anti-doublon classify/extract (substring match)
- CAPTURE_IDEE → idees/<slug>.md avec enrichissement RAG (score > 0.4)

### Routing intents
- AGENDA_ADD → POST /agenda/add → agenda.md
- AGENDA_QUERY → GET /agenda/query → réponse vocale
- DELETE_STAGING → POST /delete_staging_by_content (sémantique)
- TACHE → taches.md
- CAPTURE_PERSO → profil-personnel.md
- MEMORY validé → memory.md ou user.md

### Telegram (companion.py)
- Même pipeline que desktop : classify + extract_memory auto
- jarvis_style.md injecté dans le prompt
- Fallback Gemini complet (LLM_PROVIDER=gemini)
- /save, /search, /docs, /update, /costs, /status, /help
- Consolidation nocturne 2h, digest matinal 8h
- Staging persistant dans staging.json

### Feedback et calibration ton
- soul.md : règles contextuelles sarcasme (dispersion, procrastination, auto-évaluation), neutre (technique, sérieux), fréquence 20-30%
- jarvis_style.md : corpus TARS/HAL/JV1/JV2, 15 patterns, 8 few-shot examples
- Bouton 👍/👎 desktop → enrichit jarvis_style.md automatiquement

---

## Bugs connus
- Orbe en bol (clipping bas persistant)
- Transparence mode compact pas parfaite sur Windows (DWM)
- Références robotiques encore occasionnelles dans le ton

---

## Prochaines étapes
- 1 semaine de test en conditions réelles
- /save vocal depuis desktop
- Sprint 2 : /update user.md vocal, recherche mémoire explicite