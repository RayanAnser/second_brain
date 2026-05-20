# memory.md — Mémoire persistante

> Ce fichier est mis à jour automatiquement après chaque session.
> Il contient ce qui compte vraiment — pas tout, mais l'essentiel.
> Structure : Projets actifs → Idées en suspens → Décisions prises → Contexte personnel → Log

---

## 🔴 Projets actifs

> Ce sur quoi je travaille en ce moment. Mis à jour quand le statut change.

### Agent de traduction IA (pro)
- **Statut** : En cours — bloqué
- **Contexte** : Projet au cabinet de conseil
- **Dernière évolution** : Deux sessions consacrées à l'architecture, blocage non résolu
- **Prochaine étape** : Nommer le blocage précis (pas ce qui manque — ce qui empêche d'avancer), puis trancher l'ordre de construction : mémoire terminologique (cohérence) en premier ou adaptation contextuelle (qualité) en premier

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret (génération de pattern ? assistance en live ?)

### Compagnon IA personnel (ce système)
- **Statut** : Sprint 2 opérationnel — extraction mémoire + validation en place
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : companion.py Sprint 2 — transcription Groq, extraction auto, inline keyboard validation, logs de session
- **Prochaine étape** : Stabiliser l'usage quotidien via Telegram ; enrichir user.md avec l'export ChatGPT (en attente)
- **Stack retenue** : Obsidian (mémoire locale) + Claude Code (cerveau) + Groq Whisper (voix) + Telegram (interface mobile) + Python (skills)

### Agent d'automatisation administrative
- **Statut** : Idée — non formalisée
- **Contexte** : Automatiser des tâches administratives chronophages (périmètre à définir)
- **Dernière évolution** : Capturé en session du 2026-05-18
- **Prochaine étape** : Identifier les 2-3 tâches administratives concrètes qui bouffent le plus de temps

### OpenClaw — exploration
- **Statut** : Test local
- **Contexte** : Testé avec interface Telegram
- **Dernière évolution** : —
- **Prochaine étape** : Évaluer l'intégration dans l'architecture compagnon

---

## 🟡 Idées en suspens
| Date | Idée | Domaine | Statut |
|------|------|---------|--------|
| 2026-05-20 | Intégration Google Calendar et Proton pour synchroniser les calendriers | Compagnon IA | Capturé |
| — | — | — | — |

## 🟢 Décisions prises

> Ce qui a été décidé et ne doit pas être re-débattu à chaque session.

- **Architecture mémoire** : Obsidian + fichiers Markdown locaux (pas Notion pour la mémoire core)
- **Interface MVP** : Telegram (voice messages natifs, zéro friction mobile)
- **Modèle d'apprentissage** : Mixte — extraction auto + validation légère
- **Philosophie** : Ne pas construire from scratch inutilement — s'appuyer sur l'existant (OpenClaw, Claude Code)
- **Priorité MVP** : Mémoire persistante d'abord, relances ensuite, voice en dernier

---

## 🔵 Contexte personnel

> Ce qui influence comment je travaille en ce moment. Mis à jour si ça change.

- Mode de travail actuel : —
- Charge mentale estimée : —
- Focus du moment : Construction du compagnon IA
- Ce qui bloque en ce moment : Mise en place du cadre global

---

## 📋 Log des sessions
### Session — 2026-05-20 21:04
**Idées capturées :**
- Intégration Google Calendar et Proton pour synchronisation calendriers

**Contexte :**
- Session de découverte initiale — utilisateur demande les capacités du compagnon
- Capture d'informations personnelles (prénom, âge)

**Fils ouverts :**
- Aucun projet lancé ou décision prise — attente de direction utilisateur

### Session — 2026-05-20 20:10
**Idées capturées :**
- Connexion Google Calendar pour relances automatiques (avant événements + suivi projets inactifs)

**Fils ouverts :**
- Intégration Google Calendar : spécifications exactes à définir (type de relances, fréquence, critères de déclenchement)

### Session — 2026-05-18 21:16
**Projets mis à jour :**
- Agent de traduction → attente architecture globale + clarification du blocage actuel
- Agent d'automatisation administrative → nouveau projet capturé, statut : idée

**Fils ouverts :**
- Quelles sont les 2-3 tâches administratives concrètes qui bouffent du temps actuellement ?
- Quel est le blocage précis sur l'agent de traduction (pas ce qui manque, mais ce qui empêche d'avancer) ?

### Session — 2026-05-18 21:09
**Fils ouverts :**
- Agent de traduction : ordre de construction entre mémoire de traduction (cohérence terminologique) et adaptation contextuelle (qualité de traduction) — décision en attente
- Clarifier si contraintes projet existantes imposent un ordre de priorité

### Session — [DATE À REMPLIR]
**Sujet principal** : Framing du compagnon IA personnel
**Ce qui a été décidé** :
- Architecture cible définie (Obsidian + Claude Code + Telegram + Whisper)
- user.md créé avec profil cognitif WAIS-4 intégré
- soul.md créé — personnalité : structurant + challengeur, anti-validation
- memory.md créé — structure de mémoire persistante

**Idées capturées** :
- Inspiration : vidéo Cole Medin "AI Second Brain with Claude Code"
- Concept clé retenu : "Triade létale" OpenClaw → construire sa propre solution pour garder le contrôle
- Architecture mémoire : soul.md + user.md + memory.md + daily logs + RAG SQLite

**Fils ouverts** :
- Export ChatGPT en attente → enrichir user.md quand reçu
- Pipeline technique à construire (Sprint 1 : Telegram → Whisper → Claude)
- memory.md à alimenter au fil des sessions

**Prochaine session** : Sprint 1 — pipeline de base

### Session — 2026-05-18 21:16
**Projets mis à jour :**
- Agent de traduction → attente architecture globale + clarification du blocage actuel
- Agent d'automatisation administrative → nouveau projet capturé, statut : idée

**Fils ouverts :**
- Quelles sont les 2-3 tâches administratives concrètes qui bouffent du temps actuellement ?
- Quel est le blocage précis sur l'agent de traduction (pas ce qui manque, mais ce qui empêche d'avancer) ?

### Session — 2026-05-18 21:09
**Fils ouverts :**
- Agent de traduction : ordre de construction entre mémoire de traduction (cohérence terminologique) et adaptation contextuelle (qualité de traduction) — décision en attente
- Clarifier si contraintes projet existantes imposent un ordre de priorité


> Résumé brut de chaque session. Consolidé automatiquement dans les sections ci-dessus.

### Session — [DATE À REMPLIR]
**Sujet principal** : Framing du compagnon IA personnel
**Ce qui a été décidé** :
- Architecture cible définie (Obsidian + Claude Code + Telegram + Whisper)
- user.md créé avec profil cognitif WAIS-4 intégré
- soul.md créé — personnalité : structurant + challengeur, anti-validation
- memory.md créé — structure de mémoire persistante

**Idées capturées** :
- Inspiration : vidéo Cole Medin "AI Second Brain with Claude Code"
- Concept clé retenu : "Triade létale" OpenClaw → construire sa propre solution pour garder le contrôle
- Architecture mémoire : soul.md + user.md + memory.md + daily logs + RAG SQLite

**Fils ouverts** :
- Export ChatGPT en attente → enrichir user.md quand reçu
- Pipeline technique à construire (Sprint 1 : Telegram → Whisper → Claude)
- memory.md à alimenter au fil des sessions

**Prochaine session** : Sprint 1 — pipeline de base
