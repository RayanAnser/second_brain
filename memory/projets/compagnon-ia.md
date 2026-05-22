# Compagnon IA personnel

## Statut
**Sprint 3-5 en cours — v0.1.0 desktop déployée**

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
## Ce qui est en place (Sprints 2-5)
- Transcription voix via Groq Whisper
- Extraction automatique de mémoire en fin de session (`/save`)
- Validation inline keyboard avant écriture dans `memory.md`
- Logs de session dans `memory/logs/`
- Commandes : `/save`, `/reset`, `/status`
- **v0.1.0 desktop** : version desktop opérationnelle
- **Intégration Notion** : Token configuré ✓, recherche Notion intégrée
- **Intégration NotebookLM** : connexion recherche opérationnelle
- **GitHub Sync** : opérationnel (pull code fonctionnel)

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
- **Sprint 6 (consolidation nocturne)** : mécanisme de consolidation automatique de la mémoire
- **Sprint 7** : RAG SQLite pour recherche dans la mémoire
- Enrichir `user.md` avec l'export ChatGPT (santé, apprentissage, réflexions) — en attente de réception
- Documenter la roadmap Notion (nom du projet, catégories) dans la mémoire
- Stabiliser l'usage desktop v0.1.0

## Log
| Date | Événement |
|------|-----------||
| 2026-05-22 | **v0.1.0 desktop** — Première version desktop opérationnelle |
| 2026-05-18 | Sprint 2 opérationnel — extraction mémoire + validation inline keyboard |
| — | Sprint 1 — pipeline Telegram → Whisper → Claude |
| — | Session initiale — architecture définie, soul.md + user.md + memory.md créés |
