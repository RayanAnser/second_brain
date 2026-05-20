# Capacités du compagnon IA

## Commandes Telegram

| Commande | Description |
|----------|-------------|
| `/save` | Analyse intelligente de la session (conversation + captures stagées) → propose un plan de mise à jour des fichiers mémoire → confirmation avant écriture |
| `/reset` | Réinitialise la conversation et le log de session sans sauvegarder. Les captures stagées sont conservées. |
| `/status` | Affiche le nombre d'échanges dans la session + captures stagées en attente |
| `/update <demande>` | Propose une mise à jour de `user.md` avec confirmation. Ex : `/update je travaille maintenant sur le projet X` |

## Détection d'intention automatique

Chaque message texte ou vocal passe par une classification Haiku avant traitement.

### Intentions disponibles

| Intention | Déclencheur | Comportement |
|-----------|-------------|--------------|
| `CAPTURE_IDEE` | Idée, insight, réflexion à noter | Stagée en mémoire RAM + `staging.json`. Réponse : "Noté." |
| `CAPTURE_PROJET` | Info liée à un projet précis | Idem, hint = nom du projet |
| `CAPTURE_CONCEPT` | Définition ou explication d'un concept | Stagée avec hint "CAPTURE_CONCEPT" |
| `CAPTURE_PERSO` | Info personnelle, contexte de vie | Stagée, sera écrite dans `memory/perso/` au `/save` |
| `TACHE` | Action concrète à faire | Ajoutée immédiatement sous `## Fils ouverts` dans `memory.md` |
| `NOTION_READ` | Lire une page Notion | Contenu injecté en system prompt → réponse contextualisée |
| `NOTION_APPEND` | Ajouter du contenu à une page Notion | Append sur page ou nouvelle ligne dans database |
| `NOTION_CREATE` | Créer une nouvelle page Notion | Crée sous `NOTION_PARENT_PAGE_ID` |
| `CONVERSATION` | Tout le reste (question, discussion, conseil) | Transmis à Claude Sonnet avec historique complet |

### Exemples de messages et leur intention

- "J'ai eu une idée pour l'architecture du projet X" → `CAPTURE_PROJET`
- "Pense-à-faire : relire le contrat avant vendredi" → `TACHE`
- "Montre-moi ma roadmap Notion" → `NOTION_READ` (slug = "roadmap")
- "Ajoute 'refactoring auth' à ma todo Notion" → `NOTION_APPEND`
- "Crée une note 'Réunion du 15 mai'" → `NOTION_CREATE`
- "Qu'est-ce que tu penses de cette approche ?" → `CONVERSATION`
- "Je suis épuisé en ce moment" → `CAPTURE_PERSO`
- "Le concept de mémoire associative c'est..." → `CAPTURE_CONCEPT`

## Messages vocaux

Les messages vocaux suivent exactement le même pipeline que les textes :
1. Téléchargement du fichier `.ogg` depuis Telegram
2. Transcription via Groq `whisper-large-v3` (langue : français)
3. Classification d'intention sur la transcription
4. Dispatch selon l'intention (CAPTURE_*, TACHE, ou CONVERSATION)
5. Réponse précédée de la transcription en italique

Note : NOTION_READ/APPEND/CREATE via vocal sont traités comme CONVERSATION (pas de dispatch Notion).

## Notion

Nécessite `NOTION_TOKEN` dans les variables d'environnement.

### Résolution de page

1. Cherche d'abord dans `NOTION_PAGES` (JSON d'alias `{"nom": "page_id"}`)
2. Sinon, recherche textuelle via l'API Notion Search

### Opérations disponibles

- **Lire** une page : retourne les blocs texte (max 4000 chars)
- **Lire** une database : retourne les titres des entrées (max 50 entrées)
- **Ajouter** à une page : append des blocs paragraphe
- **Ajouter** à une database : crée une nouvelle ligne avec le titre fourni
- **Créer** une page : sous `NOTION_PARENT_PAGE_ID` avec titre + contenu

## Système de mémoire

### Staging (captures en attente)

Les CAPTURE_* ne sont jamais écrites immédiatement. Elles sont stockées :
- En RAM dans `staged_captures` (dict par user_id)
- Sur disque dans `memory/staging.json` (persistance entre redémarrages)

Au redémarrage, le bot notifie s'il y a des captures non sauvegardées.

### `/save` intelligent

1. Construit un contexte complet : conversation + captures stagées + tous les fichiers mémoire actuels
2. Appelle Claude Sonnet pour générer un plan d'opérations JSON (`ops` + `summary`)
3. Affiche le plan à l'utilisateur pour validation
4. Sur confirmation : exécute les opérations, vide les captures, réinitialise la session

### Opérations mémoire

| Mode | Effet |
|------|-------|
| `append` | Ajoute à la fin du fichier |
| `replace_section` | Remplace le contenu sous un header `## Section` |
| `replace_file` | Réécrit entièrement le fichier (usage : fichiers courts < 400 mots) |

### Fichiers mémoire

| Fichier | Rôle |
|---------|------|
| `memory/soul.md` | Personnalité et règles comportementales du compagnon |
| `memory/user.md` | Profil utilisateur (préférences, style cognitif, contexte) |
| `memory/memory.md` | Mémoire active : décisions, idées, fils ouverts, log sessions |
| `memory/projets/<slug>.md` | Un fichier par projet substantiel |
| `memory/concepts/<slug>.md` | Un fichier par concept important |
| `memory/perso/<slug>.md` | Infos personnelles structurées |
| `memory/logs/` | Transcripts bruts des sessions (non lus par le bot) |

## Heartbeat matinal

Le bot envoie un digest automatique chaque matin à **08h00** :
- Alerte si des fils ouverts datent de plus de **3 jours**
- Avertissement si `memory.md` n'a pas été mis à jour depuis plus de **7 jours**
- Projet prioritaire : projet "En cours" avec le plus de blocage ou d'urgence signalée

## GitHub sync

Si `GITHUB_TOKEN` et `GITHUB_REPO` sont définis, chaque écriture de fichier mémoire est synchronisée vers le dépôt GitHub (branche `GITHUB_BRANCH`, défaut : `main`). Permet la persistance sur Railway où le filesystem est éphémère.
