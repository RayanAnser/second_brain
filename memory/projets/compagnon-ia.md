# Compagnon IA personnel

## Statut
**Sprint 6 en cours — consolidation nocturne + optimisations déployées**

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
- Commandes : `/save`, `/reset`, `/status`, `/costs`
- **v0.1.0 validée** : mémoire connectée (Rayan, 30 ans, AI Product Builder Paris), vocal+texte Telegram
- **Intégration Notion** : Token configuré ✓, recherche Notion intégrée
- **Intégration NotebookLM** : connexion recherche opérationnelle
- **GitHub Sync** : opérationnel (pull code fonctionnel)
- **Agenda** : intents AGENDA_ADD/QUERY opérationnels, heartbeat 8h avec RDV du jour
- **TTS** : ElevenLabs turbo (~500ms)
- **Optimisations Sprint 6** :
  - Prompt caching Anthropic : -58% coûts, -1373 tokens system prompt
  - Haiku pour classify/select : -88% coûts
  - Async parallel : -300ms latence
  - Cost tracking : /costs command

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
- **Jarvis V0.1 — Deux problèmes urgents à résoudre :**
  1. Réduire la latence (actuellement trop élevée)
  2. Nettoyer le Markdown des réponses avant le TTS (balises lues à voix haute)
- **Sprint 6 (consolidation nocturne)** : mécanisme de consolidation automatique de la mémoire
- **Sprint 7** : RAG SQLite pour recherche dans la mémoire
- Enrichir `user.md` avec l'export ChatGPT (en attente)

## Log
| Date | Événement |
|------|-----------||
| 2026-05-23 | **Jarvis V0.1** — Deux problèmes identifiés : 1) Latence trop élevée 2) TTS lit les balises Markdown à voix haute (nettoyage MD requis avant TTS) |
| 2026-05-22 | **v0.1.0 desktop** — Première version desktop opérationnelle |
| 2026-05-22 | Sprint 5 terminé — intégrations Notion/NotebookLM/GitHub Sync opérationnelles |
| 2026-05-22 | Clarification intégration recherche : NotebookLM suffit, Perplexity non nécessaire |
| 2026-05-18 | Sprint 2 opérationnel — extraction mémoire + validation inline keyboard |
| — | Sprint 1 — pipeline Telegram → Whisper → Claude |
| — | Session initiale — architecture définie, soul.md + user.md + memory.md créés |
