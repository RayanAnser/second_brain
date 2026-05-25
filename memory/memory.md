# memory.md — Mémoire persistante

> Ce fichier est mis à jour automatiquement après chaque session.
> Il contient ce qui compte vraiment — pas tout, mais l'essentiel.
> Structure : Projets actifs → Idées en suspens → Décisions prises → Contexte personnel → Log

---

## 🔴 Projets actifs
> Ce sur quoi je travaille en ce moment. Mis à jour quand le statut change.

### Compagnon IA personnel (ce système)
- **Statut** : V0.1 validée — Sprint 6 (consolidation nocturne) opérationnel, optimisations coûts/latence déployées
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : Prompt caching Anthropic (-58% coûts), Haiku classify/select (-88% coûts vs Sonnet), async parallel (-300ms latence), nouveaux intents AGENDA_ADD/QUERY, heartbeat 8h, TTS ElevenLabs turbo (~500ms), cost tracking (/costs)
- **Prochaine étape** : Sprint 7 (RAG SQLite) — recherche vectorielle dans mémoire accumulée
- **Stack retenue** : Obsidian (mémoire locale) + Claude Code (cerveau) + Groq Whisper (voix) + Telegram (mobile) + Desktop v0.1.0 + Python (skills) + Notion + NotebookLM + GitHub Sync

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret

### Agent d'automatisation administrative
- **Statut** : Idée — non formalisée
- **Contexte** : Automatiser des tâches administratives chronophages
- **Dernière évolution** : Capturé en session du 2026-05-18
- **Prochaine étape** : Identifier les 2-3 tâches administratives concrètes qui bouffent le plus de temps

### OpenClaw — exploration
- **Statut** : Test local
- **Contexte** : Testé avec interface Telegram
- **Dernière évolution** : —
- **Prochaine étape** : Évaluer l'intégration dans l'architecture compagnon

### Compagnon IA personnel (ce système)
- **Statut** : Sprint 5 terminé — GitHub Sync fonctionnel
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : L'écriture sur GitHub est maintenant fonctionnelle. Plus besoin de configurer GITHUB_TOKEN ni GITHUB_REPO dans les variables d'environnement.
- **Prochaine étape** : Sprint 6 (consolidation nocturne) — mécanisme de consolidation automatique de la mémoire
- **Stack retenue** : Obsidian (mémoire locale) + Claude Code (cerveau) + Groq Whisper (voix) + Telegram (mobile) + Desktop v0.1.0 + Python (skills) + Notion + NotebookLM + GitHub Sync

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret

### Agent d'automatisation administrative
- **Statut** : Idée — non formalisée
- **Contexte** : Automatiser des tâches administratives chronophages
- **Dernière évolution** : Capturé en session du 2026-05-18
- **Prochaine étape** : Identifier les 2-3 tâches administratives concrètes qui bouffent le plus de temps

### OpenClaw — exploration
- **Statut** : Test local
- **Contexte** : Testé avec interface Telegram
- **Dernière évolution** : —
- **Prochaine étape** : Évaluer l'intégration dans l'architecture compagnon

### Compagnon IA personnel (ce système)
- **Statut** : Sprint 5 terminé — intégrations opérationnelles (Notion, NotebookLM, GitHub Sync)
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : Notion Token configuré, recherche Notion intégrée, connexion NotebookLM opérationnelle, GitHub Sync fonctionnel
- **Prochaine étape** : Sprint 6 (consolidation nocturne) — mécanisme de consolidation automatique de la mémoire
- **Stack retenue** : Obsidian (mémoire locale) + Claude Code (cerveau) + Groq Whisper (voix) + Telegram (mobile) + Desktop v0.1.0 + Python (skills) + Notion + NotebookLM

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret

### Compagnon IA personnel (ce système)
- **Statut** : Sprint 3-5 en cours — v0.1.0 desktop opérationnelle
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : Déploiement de la première version desktop (v0.1.0) en complément du système Telegram existant
- **Prochaine étape** : Stabiliser l'usage desktop ; configuration Notion (NOTION_TOKEN) ; Sprint 6 (consolidation nocturne) ; Sprint 7 (RAG SQLite)
- **Stack retenue** : Obsidian (mémoire locale) + Claude Code (cerveau) + Groq Whisper (voix) + Telegram (mobile) + Desktop v0.1.0 + Python (skills)

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret

### Agent d'automatisation administrative
- **Statut** : Idée — non formalisée
- **Contexte** : Automatiser des tâches administratives chronophages
- **Dernière évolution** : Capturé en session du 2026-05-18
- **Prochaine étape** : Identifier les 2-3 tâches administratives concrètes qui bouffent le plus de temps

### OpenClaw — exploration
- **Statut** : Test local
- **Contexte** : Testé avec interface Telegram
- **Dernière évolution** : —
- **Prochaine étape** : Évaluer l'intégration dans l'architecture compagnon

### Agent de coding musical — Strudel
- **Statut** : Expérimentation — en veille
- **Contexte** : Live coding musical avec Strudel
- **Dernière évolution** : —
- **Prochaine étape** : Définir un premier cas d'usage concret (génération de pattern ? assistance en live ?)

### Compagnon IA personnel (ce système)
- **Statut** : Sprint 2 opérationnel — extraction mémoire + validation en place
- **Contexte** : Second cerveau + mémoire persistante + voice-first français
- **Dernière évolution** : companion.py Sprint 2 — transcription Groq, extraction auto, inline keyboard validation, logs de session
- **Prochaine étape** : Stabiliser l'usage quotidien via Telegram ; enrichir user.md avec l'export ChatGPT (en attente) ; intégration Notion à faire
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
| 2026-05-20 | Explorer autres concepts Bourdieu : champ, violence symbolique, distinction | Concepts | Capturé |
| 2026-05-22 | Possibilité d'effacer/modifier certaines parties des fichiers capturés (idées périmées) | Compagnon IA | Capturé |
| 2026-05-22 | Monitoring consommation API/tokens pour éviter surprises facturation | Compagnon IA | Capturé |
| 2026-05-22 | Améliorer classification intentions : trop de messages conversationnels classés CAPTURE — renforcer détection CONVERSATION | Compagnon IA | Capturé |

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
### Session — 2026-05-22 10:55
**Sujet principal :** Physique quantique + injection d'infos personnelles

**Contexte :**
- Utilisateur demande des explications sur la physique quantique (principes fondamentaux : dualité onde-particule, incertitude, superposition, intrication, effondrement fonction d'onde)
- Demande de recherche web → pas de skill de recherche intégré actuellement
- Question stratégique sur l'injection massive d'infos personnelles (à la Hermes Agent)

**Idées capturées :**
- Trois approches pour enrichir user.md : import massif initial (export ChatGPT, notes), observation passive (calendrier Google, emails, Notion), capture conversationnelle active
- Utilisateur attend toujours l'export ChatGPT

**Fils ouverts :**
- Quelle source d'infos prioriser pour enrichir user.md ? (ChatGPT export, calendrier Google, notes Keep/Notion)
- Intégrer un skill de recherche web (Perplexity/Exa/Tavily) au compagnon ?
- Injection massive : attendre ChatGPT ou commencer par calendrier/notes ?

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

### Session — 2026-05-20 21:25
**Sujet principal** : Demande lecture roadmap Notion

**Contexte :**
- Utilisateur cherche à lire sa roadmap Notion → configuration NOTION_TOKEN manquante
- Questions sur le nom du projet et les catégories de la roadmap (info non disponible dans la mémoire)

**Capture projet (staging) :**
- Stack complet documenté : Telegram + Groq Whisper + Claude Sonnet + MD local sur Railway
- Prochaines étapes identifiées : NOTION_TOKEN .env + test Notion E2E, GitHub sync Railway, Sprint 6 (consolidation nocturne), Sprint 7 (RAG SQLite)
- Enrichissement user.md (santé, apprentissage, réflexions) en attente

**Fils ouverts :**
- Roadmap Notion : contenu et structure non documentés dans la mémoire
- Configuration Notion requise pour accès automatique (NOTION_TOKEN + NOTION_PAGES alias)

### Session — 2026-05-20 21:28
**Sujet principal** : Check rapide projets

**Contexte :**
- Utilisateur demande où il en est sur les projets
- Réponse synthèse : Agent traduction (bloqué), Strudel (veille), Compagnon IA (Sprint 2 opérationnel), Agent admin (idée)

**Capture staging :**
- Stack complète rappelée : Telegram → Groq Whisper → Claude Sonnet → Markdown local (Railway)
- TODO consolidé : NOTION_TOKEN .env + test E2E, GitHub sync Railway, Sprint 6 (consolidation nocturne), Sprint 7 (RAG SQLite), enrichir user.md

**Fils ouverts :**
- Aucun fil nouveau ouvert — session de check status uniquement

## Fils ouverts
- Supprimer l'agent de traduction de la liste


- Mardi 9 juin à 17h : rendez-vous avec Ségolène
- Vérifier s'il y a un cinéma qui projette Fenêtres sur cour dans Paris
- Repas demain à midi avec les potes de prépa
- Ajouter un test 'Marseille 2' pour les captures en attente dans l'environnement staging
- Ajouter test de bord de haut dans les trucs en staging
- Garder les éléments en attente, effacer après validation du système. Tester Montpellier.
- Ajouter une note sur le PQ et acheter du shampoing
### Session — 2026-05-20 21:32
**Sujet principal** : Check rapide identité

**Contexte :**
- Utilisateur demande son prénom (test mémoire basique)
- Réponse correcte : Rayän

**Capture :**
- Préférence alimentaire : sushis

**Fils ouverts :**
- Aucun

### Session — 2026-05-20 21:38
**Sujet principal** : Questions exploratoires — couleur préférée, origine, fonctionnement mémoire

**Contexte :**
- Utilisateur teste la mémoire (couleur préférée, origine)
- Demande d'explication du système de capture staging + fichiers mémoire

**Capture :**
- Couleur préférée : vert (consolidée dans user.md)

**Fils ouverts :**
- Aucun

| 2026-05-20 | Explorer d'autres concepts Bourdieu (habitus, champ, violence symbolique…) | Concepts | Capturé |

### Session — 2026-05-20 21:40
**Sujet principal** : Exploration concepts Bourdieu (capitaux)

**Contexte :**
- Demande d'exploration des différents concepts Bourdieu
- Focus sur les 4 types de capitaux (économique, culturel, social, symbolique)
- Explication des formes du capital culturel (incorporé, objectivé, institutionnalisé)
- Conversions possibles entre capitaux

**Capture :**
- Nouveau fichier `memory/concepts/bourdieu-capitaux.md` créé
- Connexions identifiées avec projets compagnon IA, agent traduction, Strudel

**Fils ouverts :**
- Exploration d'autres concepts Bourdieu (habitus, champ, violence symbolique) à venir
- Quel capital creuser en priorité ou quelle application aux projets en cours ?


### Session — 2026-05-20 21:44
**Sujet principal** : Question exploration en cours

**Contexte :**
- Utilisateur demande ce qu'il explore en ce moment
- Réponse : Bourdieu et les capitaux (4 types + conversions)

**Fils ouverts :**
- Quel capital approfondir en priorité ?
- Appliquer les concepts Bourdieu à un projet existant ?


### Session — 2026-05-22 18:05
**Sujet principal :** Amélioration système compagnon IA — deux axes identifiés

**Captures stagées :**
- Détection intentions : problème actuel = intentions détectées ne correspondent pas toujours aux attentes réelles, système passe à côté de la vraie demande
- Architecture mémoire : besoin d'optimiser lecture concepts, organisation fichiers, architecture globale (système fonctionnel mais potentiel d'amélioration)

**Décision :** Aucune pour l'instant — réflexion sur la priorisation entre les deux axes

**Fils ouverts :**
- Quel axe traiter en premier : intentions ou architecture ?
- Comment analyser concrètement comment l'utilisateur réfléchit et formule ses demandes ?


### Session — 2026-05-22 18:30
**Sujet principal :** Bilan compagnon IA

**État actuel :**
- Stack complète opérationnelle (Telegram, Groq, Claude, MD local, Desktop v0.1.0)
- Fonctionnalités actives : transcription voix, extraction mémoire, logs, commandes `/save`, `/reset`, `/status`
- Intégrations configurées : Notion ✓, NotebookLM ✓, GitHub Sync ✓

**Décisions prises :**
- Retrait du projet Agent de traduction de la liste active (archivé)

**Observation clé :**
- Système techniquement fonctionnel mais pas encore utilisé quotidiennement de manière naturelle (2-3/10)
- Utilisateur en phase d'exploration — évalue l'utilité et comment l'intégrer dans le workflow

**Fils ouverts :**
- Identifier le frein réel : technique (feature manquante) / habitude (interface pas fluide) / usage (pas clair concrètement) ?
- Sprint 6 (consolidation nocturne) : toujours en attente
- Sprint 7 (RAG SQLite) : roadmap claire, pas encore fait


### Session — 2026-05-22 18:39
**Sujet principal :** Clarification identité du compagnon IA

**Contexte :**
- Question utilisateur : « J'aurais besoin d'en savoir plus sur mon compagnon RIA »
- Clarification : le compagnon IA, c'est ce système lui-même (Obsidian + Claude Code + Telegram + Groq Whisper)
- État actuel : stack complète opérationnelle, version desktop v0.1.0, intégrations Notion/NotebookLM/GitHub Sync

**Captures stagées :**
- [CAPTURE_IDEE] Système de monitoring consommation API/tokens (éviter surprises facturation AXA/autres services)
- [CAPTURE_IDEE] Problème classification : trop de messages conversationnels classés en CAPTURE au lieu de CONVERSATION — besoin d'améliorer sensibilité détection CONVERSATION

**Fils ouverts :**
- Monitoring API/tokens : solution à définir
- Classification intentions : améliorer la détection CONVERSATION vs CAPTURE

**Observation :**
- Utilisateur utilise « RIA » au lieu de « IA » — probablement une simple typo, pas une nouvelle terminologie à retenir


| 2026-05-22 | Monitoring consommation API/tokens pour éviter surprises facturation (actuellement pas de visibilité) | Compagnon IA | Capturé |
| 2026-05-22 | Améliorer classification intentions : trop de messages conversationnels classés CAPTURE — renforcer détection CONVERSATION | Compagnon IA | Capturé |

### Session — 2026-05-22 23:23
**Sujet principal :** Résumé des projets en cours

**Contexte :**
- Utilisateur demande un état des lieux global des projets
- Réponse fournie avec statut actuel de 4 projets : Compagnon IA (actif, Sprint 5 terminé), Strudel (en veille), Agent admin (idée non formalisée), OpenClaw (exploration locale)
- Agent de traduction retiré de la liste (archivé 2026-05-22)

**Capture stagée :**
- [CAPTURE_PROJET] Continuer Sprint 6 + intégration desktop pour améliorer l'expérience utilisateur

**Observation :**
- Seul le compagnon IA avance concrètement — les autres projets sont bloqués ou en veille faute de périmètre défini
- Utilisateur a clairement identifié Sprint 6 (consolidation nocturne) comme prochaine étape prioritaire

**Fils ouverts :**
- Débloquer les projets en veille (Strudel, Agent admin) ou continuer sur Sprint 6 ?
- Amélioration expérience desktop (prochaine itération à définir)

### Session — 2026-05-22 23:33
**Sujet principal :** Exploration OpenClaw / Hermes — clarification du besoin réel

**Contexte :**
- Recherche demandée sur OpenClaw / Hermes → clarification intégration Perplexity vs NotebookLM
- Utilisateur confirme : NotebookLM suffit (cherche dans sources uploadées) ; Perplexity non nécessaire (recherche web temps réel)
- Décision : ne pas ajouter Perplexity

**Captures stagées :**
- [CAPTURE_IDEE] Améliorer l'expérience desktop : réponses plus rapides, meilleure qualité de voix, expérience seamless et fluide (2026-05-22 23:27)
- [CAPTURE_IDEE] Besoin d'un hub centralisé pour : capturer pensées et idées vocalement, lancer des recherches, exécuter des idées et récupérer l'output. Principe clé : tout centralisé, contrôle en backend. (2026-05-22 23:30)
- [CAPTURE_IDEE] Idée d'intégrer Patelexity au workflow de recherche existant (NotebookLM + AIM), pour compléter le triangle méthodologique de recherche approfondie (2026-05-22 23:31)
- [CAPTURE_IDEE] Explorer comment combiner les créations faites avec Hermes et OpenClaw pour maximiser leur synergie et leur impact. (2026-05-22 23:33)

**Fils ouverts :**
- OpenClaw / Hermes : l'utilisateur voulait une recherche → besoin clarifié = NotebookLM suffit pour l'instant
- Les 4 idées capturées ne sont pas développées — pas d'action concrète définie

**Observation :**
- L'utilisateur a exploré OpenClaw/Hermes mais n'a pas tranché de besoin réel : ni recherche web, ni intégration de skills externes
- NotebookLM reste l'outil de recherche privilégié (sources uploadées = connaissances accumulées)
- Les captures staging ne seront probablement pas toutes consolidées — attendre que l'utilisateur revienne dessus


### Session — 2026-05-22 23:38
**Sujet principal :** Problème détection d'intention Notion

**Contexte :**
- Utilisateur signale un problème récurrent : dès qu'il pose une question qui ressemble à "cherche X", le système déclenche NOTION_READ alors qu'il veut une réflexion ou une vraie recherche (NotebookLM, web, ou juste discuter)
- Détection trop large : interprète toute demande de recherche comme une demande Notion

**Idée capturée :**
- Possibilité de répondre directement aux messages vocaux dans le chat (actuellement non codable dans ce contexte)

**Fils ouverts :**
- Durcir la détection NOTION_READ : ne déclencher QUE si mention explicite de Notion ("Montre-moi ma roadmap Notion", "Lis ma page Notion X", "Qu'est-ce qu'il y a dans Notion sur Y")
- Tout le reste → CONVERSATION par défaut
- Solution immédiate : coder maintenant ou attendre exemples concrets de messages qui ont foiré ?

### Session — 2026-05-22 23:45
**Sujet principal :** État des lieux global + test d'usage du compagnon IA

**Contexte :**
- Demande de récap complet des projets en cours
- Constat : un seul projet actif (Compagnon IA, Sprint 5 terminé), tout le reste en veille ou non formalisé
- Problème sous-jacent identifié : le compagnon fonctionne techniquement, mais utilisé peu (2-3/10)
- Question clé : **pourquoi l'utilisateur n'utilise pas le compagnon au quotidien ?**
- Réponse utilisateur : **c'est l'usage — se demande comment l'utiliser au mieux**

**5 cas d'usage concrets proposés :**
1. Capture vocale d'idées en mouvement (remplacer Google Keep/notes perdues)
2. Déblocage quand ça tourne en rond (forcer à nommer le blocage précis)
3. Relances sur ce qui est abandonné (finir ou choisir consciemment de lâcher)
4. Relier les idées entre elles (construire une vision profonde)
5. Structurer le chaos en fin de session (valider ce qui mérite d'être retenu)

**Test proposé :** Envoyer un message vocal par jour pendant 7 jours, sans obligation de `/save`, juste tester la capture.

**Capture staging :**
- [CAPTURE_IDEE] Exploration du système de mémoire : test des fonctionnalités de stockage et utilisation comme outil de réflexion et d'aide à la pensée (2026-05-22 23:43)

**Fils ouverts :**
- Test 7 jours : l'utilisateur va-t-il le faire ou préférer creuser autre chose avant ?
- Si le test est fait, évaluer à la fin de la semaine si ça apporte quelque chose ou si c'est une contrainte de plus

**Observation clé :**
- L'utilisateur est en phase d'exploration, pas encore d'habitude installée
- Le vrai blocage n'est pas technique — c'est le flou sur **quoi faire avec le compagnon au quotidien**
- Les 5 cas d'usage sont des hypothèses à tester, pas des certitudes


### Session — 2026-05-23 00:08
**Sujet principal :** Premier usage intensif du compagnon — clarification de l'usage réel

**Contexte :**
- Utilisateur demande où on en est → constat : système opérationnel, mais utilisé très peu (2-3/10)
- Raison identifiée : **flou sur l'usage concret au quotidien** — pas de blocage technique, mais manque de clarté sur quoi faire avec le compagnon
- **Premier usage réel aujourd'hui :** nombreux messages vocaux envoyés pour capturer idées et tester le système
- Besoin confirmé : **un lieu unique de centralisation** pour tout regrouper

**Cas d'usage testés/évoqués :**
- Capture d'idées vocales en mouvement
- Déblocage quand ça tourne en rond
- Relances sur idées/projets abandonnés
- Connexion entre idées
- Structuration du chaos en fin de session

**Test proposé (pas encore fait) :**
- Envoyer 1 message vocal par jour pendant 7 jours, sans obligation de `/save`, juste pour évaluer l'utilité

**Décision :**
- Pas de décision ferme — l'utilisateur explore encore l'usage possible
- Le compagnon fonctionne techniquement, maintenant il faut comprendre **comment l'utiliser au mieux**

**Fils ouverts :**
- Test 7 jours : à faire ou pas ?
- Continuer sur Sprint 6 (consolidation nocturne) ou clarifier d'abord un cas d'usage ultra-concret ?

**Observation :**
- Première vraie session d'usage intensif depuis le déploiement
- L'utilisateur a testé le système massivement aujourd'hui (2026-05-23) → validation que le besoin de centralisation existe


### Session — 2026-05-24 11:35
**Sujet principal :** Mise à jour GitHub Sync

**Capture stagée :**
- [CAPTURE_PROJET] L'écriture sur GitHub est maintenant fonctionnelle. Plus besoin de configurer GITHUB_TOKEN ni GITHUB_REPO dans les variables d'environnement.

**Statut projet Compagnon IA :**
- Sprint 5 terminé — GitHub Sync opérationnel
- Configuration simplifiée (pas de variables d'environnement nécessaires)
- Stack complète : Obsidian + Claude Code + Groq Whisper + Telegram + Desktop v0.1.0 + Python + Notion + NotebookLM + **GitHub Sync ✓**

**Observation :**
- Évolution technique notable — passage d'une configuration manuelle à un système automatisé
- Prochaine étape : Sprint 6 (consolidation nocturne)


### Session — 2026-05-24 23:38
**Sujet principal :** Tests système staging et retours utilisateur

**Contexte :**
- Utilisateur teste le système de staging des captures (CAPTURE_IDEE)
- Premier test : idée générique pour valider le fonctionnement
- Deuxième test : idée spécifique JSON pour valider format
- Demande de résumé en fin de session

**Captures stagées :**
- [CAPTURE_IDEE] Idée à explorer pour un test (2026-05-24 23:38)
- [CAPTURE_IDEE] Idée à explorer pour un test de staging JSON (2026-05-25 00:04)

**Observation :**
- Aucun contenu réel capturé — session purement technique de validation système
- Fonctionnement staging confirmé opérationnel

**Fils ouverts :**
- Aucun — session test système uniquement

### Session — 2026-05-25 00:09
**Sujet principal :** Optimisations techniques Jarvis — Sprint 6 consolidation nocturne

**Captures stagées :**
- Prompt caching Anthropic déployé : -58% coûts, -1373 tokens system prompt
- Haiku pour classify/select : -88% coûts vs Sonnet
- Async parallel : -300ms latence
- Nouveaux intents opérationnels : AGENDA_ADD, AGENDA_QUERY
- Heartbeat 8h avec RDV du jour
- TTS ElevenLabs turbo (~500ms)
- Cost tracking en place (/costs)
- V0.1 validé : mémoire connectée (Rayan, 30 ans, AI Product Builder Paris), vocal+texte Telegram
- Sprint 7 RAG SQLite prévu

**Statut projet Compagnon IA :**
- Sprint 6 (consolidation nocturne) en cours
- Stack validée : Telegram, Groq Whisper, Claude Sonnet/Haiku, MD local, Desktop v0.1.0, Python, Notion, NotebookLM, GitHub Sync
- Optimisations coûts/latence déployées
- Vocal fluide (transcription + TTS)
- Agenda synchronisé (intents opérationnels)

**Observation :**
- Session purement technique — optimisations infra + validation V0.1
- Système de plus en plus fluide (coûts, latence, vocal)
- Prochaine étape : RAG SQLite (Sprint 7)

**Fils ouverts :**
- Sprint 7 (RAG SQLite) à lancer
- Monitoring coûts : suivi long terme à faire


### Session — 2026-05-25 00:14
**Sujet principal :** Validation mémoire + archivage agent traduction

**Contexte :**
- Consolidation globale de la mémoire après Sprint 6
- Archivage agent traduction confirmé (décision 2026-05-22 validée)
- V0.1 Jarvis opérationnelle : mémoire connectée, vocal fluide, agenda synchronisé, cost tracking en place
- Stack validée : Telegram + Groq Whisper + Claude Sonnet/Haiku + MD local + Desktop v0.1.0 + Python + Notion + NotebookLM + GitHub Sync

**Optimisations Sprint 6 :**
- Prompt caching Anthropic : -58% coûts (25k tokens system cachés)
- Haiku pour classify/select : -88% coûts vs Sonnet
- Async parallel classify+select : -300ms latence
- Nouveaux intents opérationnels : AGENDA_ADD, AGENDA_QUERY (écriture/lecture agenda.md sans appel Claude)
- Heartbeat 8h avec RDV du jour
- TTS ElevenLabs turbo (~500ms)
- Cost tracking actif (/costs)

**Fils ouverts :**
- Sprint 7 (RAG SQLite) : prochaine étape sur roadmap
- Monitoring coûts long terme : suivi à faire

**Observation :**
- Système stable, usage quotidien à valider dans durée
- Aucune nouvelle idée capturée — session de consolidation technique uniquement


### Session — 2026-05-25 15:54
**Sujet principal :** Test manuel système de consolidation mémoire

**Contexte :**
- Capture staging d'un test manuel (2026-05-25 15:51)
- Aucune conversation substantielle
- Session technique — validation fonctionnement système

**Observation :**
- Test système uniquement — aucun contenu réel à retenir

**Fils ouverts :**
- Aucun
