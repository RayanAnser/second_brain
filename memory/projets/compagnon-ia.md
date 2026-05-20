# Compagnon IA personnel

## Statut
**Sprint 2 opérationnel**

## Contexte
Second cerveau personnel + mémoire persistante + interface voice-first en français. Inspiré par la vidéo Cole Medin "AI Second Brain with Claude Code" et le concept de "Triade létale" OpenClaw (construire sa propre solution pour garder le contrôle).

## Stack retenue
| Composant | Rôle |
|-----------|------|
| Obsidian | Mémoire locale (fichiers Markdown) |
| Claude Code | Cerveau — raisonnement + construction |
| Groq Whisper (`whisper-large-v3`) | Transcription voix → texte |
| Telegram | Interface mobile, voice messages natifs |
| Python (`companion.py`) | Glue technique |

## Ce qui est en place (Sprint 2)
- Transcription voix via Groq Whisper
- Extraction automatique de mémoire en fin de session (`/save`)
- Validation inline keyboard avant écriture dans `memory.md`
- Logs de session dans `memory/logs/`
- Commandes : `/save`, `/reset`, `/status`

## Architecture mémoire
| Fichier | Rôle |
|---------|------|
| `memory/soul.md` | Personnalité du compagnon |
| `memory/user.md` | Profil cognitif + contexte utilisateur |
| `memory/memory.md` | Projets, décisions, logs de session |
| `memory/logs/` | Transcripts bruts (non lus par le bot) |

## Décisions prises (ne pas re-débattre)
- Markdown local, pas Notion pour la mémoire core
- Telegram comme interface MVP (zéro friction mobile)
- Modèle mixte : extraction auto + validation légère
- Ne pas construire from scratch si l'existant suffit (OpenClaw, Claude Code)
- Ordre de priorité MVP : mémoire persistante → relances → voice

## Prochaine étape
## Prochaine étape
- **Sprint 3-5 (actuel)** : Configuration Notion (NOTION_TOKEN .env + test E2E), GitHub sync Railway
- **Sprint 6** : Consolidation nocturne automatique
- **Sprint 7** : RAG SQLite pour recherche dans la mémoire
- Enrichir `user.md` avec l'export ChatGPT (santé, apprentissage, réflexions) — en attente de réception
- Documenter la roadmap Notion (nom du projet, catégories) dans la mémoire

## Log
| Date | Événement |
|------|-----------|
| 2026-05-18 | Sprint 2 opérationnel — extraction mémoire + validation inline keyboard |
| — | Sprint 1 — pipeline Telegram → Whisper → Claude |
| — | Session initiale — architecture définie, soul.md + user.md + memory.md créés |
