# recherche-rag

_Généré le 2026-05-22 11:31_

## Sources

- https://latenode.com/blog/ai-frameworks-technical-infrastructure/rag-retrieval-augmented-generation/rag-architecture-complete-guide-to-retrieval-augmented-generation-components
- https://architecture.learning.sap.com/docs/ref-arch/e5eb3b9b1d/3
- https://medium.com/@harsh0701/retrieval-augmented-generation-rag-explained-architecture-retrieval-and-generation-ba2d7239133e
- https://link.springer.com/article/10.1007/s12599-025-00945-3
- https://arxiv.org/pdf/2506.00054

## Synthèse

La **Génération Augmentée par Récupération (RAG)** est une architecture hybride qui combine les capacités génératives des grands modèles de langage (LLM) avec des mécanismes de récupération de données en temps réel [1, 2]. Ce système permet de pallier les limites des modèles classiques, comme les **hallucinations** ou l'obsolescence des informations, en ancrant les réponses dans des sources externes vérifiables [3-5].

### 1. Concepts Fondamentaux
*   **Mémoire Paramétrique vs Non-Paramétrique :** Les LLM s'appuient sur une mémoire **paramétrique** (connaissances figées lors de l'entraînement) [6]. Le RAG y ajoute une mémoire **non-paramétrique** sous forme d'une base de connaissances externe (fichiers PDF, bases de données, sites web) qui peut être mise à jour sans réentraîner le modèle [1, 7, 8].
*   **Le Pipeline "Retriever-Generator" :** Le processus se décompose généralement en trois phases : la **récupération** (trouver les documents pertinents), l'**augmentation** (intégrer ces documents au prompt de l'utilisateur) et la **génération** (produire la réponse finale via le LLM) [9, 10].
*   **Embeddings et Recherche de Similarité :** Pour que le système comprenne quels documents sont pertinents, le texte est converti en vecteurs numériques (**embeddings**) [11, 12]. Une recherche de similarité (souvent la similarité cosinus) permet de trouver les segments de texte dont le sens est le plus proche de la requête de l'utilisateur [13-15].

### 2. Architecture et Composants Clés
Un système RAG standard repose sur plusieurs briques essentielles :
*   **Ingestion de données :** Collecte, découpage (chunking) et prétraitement des documents bruts [11, 16].
*   **Base de données vectorielle :** Stockage et indexation des embeddings pour une recherche rapide (ex: SAP HANA Cloud, Milvus, Pinecone) [11, 12, 17].
*   **Moteur de récupération :** Identifie les **Top-K** passages les plus pertinents [10, 11].
*   **Générateur :** Le LLM qui synthétise une réponse en utilisant à la fois sa logique interne et le contexte fourni [11, 18].

### 3. Variantes et Évolutions
Les sources distinguent plusieurs niveaux de complexité :
*   **RAG Simple :** Un flux linéaire allant de la requête à la génération [19].
*   **RAG Adaptatif et Correctif (CRAG) :** Utilise des boucles de rétroaction pour évaluer la qualité des documents récupérés et décider s'il faut déclencher une nouvelle recherche ou décomposer la requête [20-22].
*   **RAG Multi-modal :** Capable de traiter et de décrire des **images** contenues dans les documents pour enrichir la réponse textuelle [23, 24].
*   **GraphRAG :** Utilise des **graphes de connaissances** pour mieux comprendre les relations complexes entre les entités, réduisant les hallucinations de 20 à 30 % [25, 26].

### 4. Informations Pratiques et Avantages
*   **Réduction des coûts :** Le RAG est nettement moins coûteux et moins gourmand en ressources que le **fine-tuning** (ajustement fin) d'un modèle [27, 28].
*   **Transparence et Citations :** Contrairement aux modèles "vanilla", le RAG peut fournir des **liens directs** ou des références vers les documents sources, ce qu'on appelle le **grounding** (ancrage) [4, 29, 30].
*   **Implémentation facilitée :** Des plateformes comme **Latenode** permettent de transformer des diagrammes théoriques en flux de travail interactifs sans code [31, 32]. SAP propose également des services de "Grounding" prêts à l'emploi via **SAP AI Core** [33, 34].

### 5. Défis à Surveiller
*   **Qualité des données :** Le système est sensible au bruit et aux informations contradictoires présentes dans la base de connaissances [35, 36].
*   **Effet "Blinkered Chunk" :** Si le découpage du texte est trop fin, le modèle peut perdre le contexte global du document [37].
*   **Latence :** L'étape de récupération et de traitement des documents peut ralentir le temps de réponse initial [35, 38].

Souhaitez-vous que je crée un questionnaire pour tester vos connaissances sur ces concepts ou un rapport détaillé sur une architecture spécifique ?

## NotebookLM

- notebook_id: `940b76fe-1895-46f9-a350-49525a0f7fcf`
