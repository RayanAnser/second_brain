# Compagnon IA Personnel — Setup Sprint 1

## Structure des fichiers

```
ton-projet/
├── companion.py          # Le bot
├── requirements.txt      # Dépendances
└── memory/               # Tes fichiers Obsidian (ou copies)
    ├── user.md           # Qui tu es
    ├── soul.md           # Comment il se comporte
    └── memory.md         # Mémoire persistante
```

## Installation

```bash
# 1. Crée un environnement virtuel
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 2. Installe les dépendances
pip install -r requirements.txt
```

## Configuration

Crée un fichier `.env` ou exporte ces variables :

```bash
export TELEGRAM_TOKEN="ton_token_botfather"
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."          # Pour Whisper
export MEMORY_DIR="./memory"            # Chemin vers tes fichiers md
```

Ou avec un fichier `.env` + python-dotenv :
```bash
pip install python-dotenv
```
Et ajoute en haut de `companion.py` :
```python
from dotenv import load_dotenv
load_dotenv()
```

## Fichiers mémoire

Place tes `user.md`, `soul.md`, `memory.md` dans le dossier `memory/`.
Si tu utilises Obsidian, pointe `MEMORY_DIR` directement vers ton vault.

## Lancement

```bash
python companion.py
```

## Utilisation

| Action | Comment |
|--------|---------|
| Message texte | Tape directement |
| Message vocal | Maintiens le micro dans Telegram — transcrit automatiquement |
| Réinitialiser la conversation | `/reset` |

## Ce que fait Sprint 1

✅ Reçoit texte et voix
✅ Transcrit le français via Whisper
✅ Injecte user.md + soul.md + memory.md dans chaque réponse
✅ Maintient l'historique de conversation en mémoire

## Ce qui vient ensuite (Sprint 2)

- Écriture automatique dans memory.md après chaque session
- Extraction des idées importantes
- Interface de validation ("garder ça ?")
