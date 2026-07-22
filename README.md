# Plateforme de pilotage commercial et financier

Plateforme data & IA end-to-end pour l'analyse des ventes/achats issus de
l'ERP de l'entreprise : ingestion générique pilotée par configuration,
fiabilisation des données, analyse de marge, détection d'anomalies et
prévision de la demande.


---

## 1. Pourquoi ce projet (contexte métier)

L'entreprise dispose de données Ventes/Achats dans son ERP Microsoft
Dynamics, mais sans accès direct pour un tiers, sans vue consolidée de la
marge réelle par article, et sans outil de détection automatique
d'anomalies (ventes à perte, ruptures de saisie) ni de prévision de la
demande. Ce projet construit une plateforme qui répond à ces trois
besoins, de façon réutilisable au-delà du seul stage.

## 2. Principe d'architecture : généricité vs logique métier

Le pipeline est volontairement séparé en deux couches, pour qu'il reste
exploitable par l'entreprise même si le format d'export change, ou
qu'un nouveau domaine de données (RH, produits...) doive être ajouté un jour :

```
┌─────────────────────────────────────────────────────────┐
│  COUCHE GÉNÉRIQUE (config-driven, ne connaît aucun métier) │
│  config/*.yaml → connecteurs → validation → chargement    │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  COUCHE MÉTIER (dbt + Python, spécifique à un domaine)     │
│  module Ventes/Achats : marge, ABC, anomalies, prévision  │
└─────────────────────────────────────────────────────────┘
```

**Règle simple appliquée dans tout le code** : aucun nom de colonne du
fichier source n'est écrit en dur dans le code Python. Tout passe par un
fichier de configuration YAML (`config/sources/*.yaml`). Pour brancher un
nouvel extrait ERP (colonnes renommées, réordonnées, format différent), il
suffit de dupliquer ce fichier et d'ajuster le mapping — **aucune ligne de
code à modifier**. Ce principe a été testé et validé (voir section
[Tests de généricité](#tests-de-généricité)).

## 3. Arborescence du projet

```
erp-platform/
├── config/
│   └── sources/
│       └── erp_ventes_achats.yaml   # mapping + schéma + règles métier d'une source
├── ingestion/                       # COUCHE GÉNÉRIQUE
│   ├── connectors/
│   │   └── excel_connector.py       # lecture Excel -> DataFrame normalisé
│   ├── core/
│   │   ├── config_loader.py         # chargement des fichiers YAML
│   │   ├── validator.py             # validation générique de schéma
│   │   └── loader.py                # écriture Postgres (ou Parquet en repli local)
│   ├── main.py                      # orchestrateur : config -> connecteur -> validation -> chargement
│   └── requirements.txt
├── dbt/
│   └── erp_platform/                # COUCHE MÉTIER (modélisation, à développer en Phase 1 suite)
│       └── models/
│           ├── staging/             # nettoyage : signes, unités, retours
│           └── marts/               # marge, ABC, faits/dimensions
├── data/
│   ├── raw/                         # fichiers sources (jamais versionnés, voir .gitignore)
│   └── processed/                   # sorties locales (Parquet) quand pas de base connectée
├── docs/
│   └── data_dictionary.md           # dictionnaire de données de la source actuelle
├── docker-compose.yml               # PostgreSQL local
├── .env.example                     # variables d'environnement à copier en .env
└── README.md
```

## 4. Démarrage rapide

### Prérequis
- Python 3.10+
- Docker + Docker Compose (pour la base PostgreSQL)

### Installation

```bash
git clone <url-du-repo>
cd erp-platform
python3 -m venv .venv && source .venv/bin/activate
pip install -r ingestion/requirements.txt

cp .env.example .env   # puis adapter les identifiants si besoin
docker compose up -d   # démarre PostgreSQL
```

### Lancer l'ingestion

Placer le fichier Excel source dans `data/raw/` puis :

```bash
python -m ingestion.main --source config/sources/erp_ventes_achats.yaml
```

Le script :
1. charge la configuration de la source,
2. lit le fichier via le connecteur Excel,
3. valide le schéma (colonnes obligatoires, valeurs autorisées, unicité de clé),
4. charge les données dans PostgreSQL (`raw.erp_ventes_achats`), ou en
   Parquet local dans `data/processed/` si aucune base n'est connectée
   (`DATABASE_URL` absent) — utile pour développer sans Docker.

Exemple de sortie réelle (testée sur l'extrait 2017-2019, 71 588 lignes) :

```
[1/4] Chargement de la configuration : config/sources/erp_ventes_achats.yaml
      Source : Écritures comptables Ventes/Achats (ERP) (id=erp_ventes_achats)
[2/4] Lecture via connecteur 'excel' : data/raw/erp_extrait_2019.xlsx
      71588 lignes lues, 12 colonnes normalisées
[3/4] Validation du schéma
Validation 'erp_ventes_achats' — 71588 lignes
  Statut : OK
  [WARN] Clé métier ['numero_document', 'numero_article'] : 12418 ligne(s) impliquée(s) dans un doublon
[4/4] Chargement vers le stockage brut
      Terminé -> parquet:data/processed/erp_ventes_achats.parquet (71588 lignes)
```

## 5. Tests de généricité

Pour valider que le pipeline ne dépend pas d'un format de fichier figé, un
test a été effectué avec une copie du fichier source dont les colonnes ont
été **renommées et réordonnées** (simulant un futur export différent) :

- Nouveau fichier de config (`erp_ventes_achats_v2.yaml`) avec un mapping ajusté
- **Aucune modification du code Python**
- Résultat : les 71 588 lignes sont lues, validées et chargées correctement

C'est la preuve que le pipeline est exploitable par l'entreprise même si
le format d'export ERP évolue, sans réécriture du projet.

## 6. Ajouter une nouvelle source de données

1. Créer un nouveau fichier `config/sources/ma_nouvelle_source.yaml` en
   s'inspirant de `erp_ventes_achats.yaml` (mapping, schéma, règles métier).
2. Si le format est déjà supporté (Excel), rien d'autre à faire.
   Sinon, ajouter un connecteur dans `ingestion/connectors/` respectant
   l'interface `read(source_config, file_path) -> DataFrame`.
3. Lancer : `python -m ingestion.main --source config/sources/ma_nouvelle_source.yaml`

## 7. Données traitées

Voir [`docs/data_dictionary.md`](docs/data_dictionary.md) pour le détail
des colonnes, des valeurs observées et des points de vigilance identifiés
sur les données réelles (convention de signe, retours, unités hétérogènes,
doublons apparents).

## 8. Feuille de route

- [x] **Phase 1 — Ingestion générique** : connecteur Excel, validation de
      schéma, chargement config-driven, testé sur données réelles (71 588 lignes)
- [x] **Test de généricité intra-domaine** : pipeline validé sur un format
      de fichier différent (colonnes renommées/réordonnées) sans modification de code
- [ ] **Modélisation dbt** : nettoyage (signes, unités, retours), schéma
      en étoile (`fact_transactions`, `dim_article`, `dim_date`, `dim_unite`)
- [ ] **Module métier Ventes/Achats** : marge brute par article, analyse
      ABC/Pareto, détection d'anomalies (ventes à perte, saisies suspectes)
- [ ] **Prévision de la demande** (Prophet) par article/famille
- [ ] **Orchestration automatisée** (n8n) du pipeline complet
- [ ] **Dashboards Power BI** (marge, anomalies, prévisions)
- [ ] **Généralisation multi-domaines** (perspective) : validation du
      moteur générique sur un 2ᵉ domaine (RH, produits...)
- [ ] **Sécurité & Cloud** (perspective) : Azure Key Vault, ADLS, Azure ML

## 9. Stack technique

| Domaine | Outil |
|---|---|
| Ingestion | Python (pandas, openpyxl, PyYAML) |
| Stockage | PostgreSQL (Docker) |
| Transformation / modélisation | dbt |
| Machine Learning | Scikit-Learn (Isolation Forest), Prophet |
| Orchestration | n8n |
| Visualisation | Power BI |
| Sécurité / Cloud (perspective) | Azure Key Vault, ADLS, Azure ML |

## 10. Choix d'architecture — pourquoi pas un outil d'ingestion existant (Airbyte, Fivetran) ?

Ces outils existent et sont utilisés en entreprise, mais ils ne
couvrent que l'extraction/chargement — jamais la logique métier
(marge, anomalies, prévision) qui est le cœur de valeur de ce projet.
Le connecteur générique développé ici s'inspire de leur architecture
(principe "tap/target" : un connecteur interchangeable par source), à une
échelle adaptée à un projet de stage, tout en gardant la maîtrise complète
du code plutôt que de dépendre d'une plateforme externe.

```
erp-platform
├─ config
│  └─ sources
│     └─ erp_ventes_achats.yaml
├─ data
├─ dbt
│  └─ erp_platform
│     ├─ dbt_project.yml
│     ├─ models
│     │  ├─ intermediate
│     │  │  ├─ int_achats_par_article.sql
│     │  │  ├─ int_retours_par_article.sql
│     │  │  ├─ int_ventes_par_article.sql
│     │  │  └─ _intermediate.yml
│     │  ├─ marts
│     │  │  ├─ dim_article.sql
│     │  │  ├─ dim_date.sql
│     │  │  ├─ dim_unite.sql
│     │  │  ├─ fact_transactions.sql
│     │  │  ├─ mart_abc_article.sql
│     │  │  ├─ mart_anomalies_ventes.sql
│     │  │  ├─ mart_marge_article.sql
│     │  │  └─ _marts.yml
│     │  └─ staging
│     │     ├─ stg_erp_ventes_achats.sql
│     │     ├─ _erp_sources.yml
│     │     └─ _stg_erp_ventes_achats.yml
│     ├─ package-lock.yml
│     ├─ packages.yml
│     ├─ profiles.yml.example
│     └─ seeds
│        └─ unite_conversion.csv
├─ docker-compose.yml
├─ docs
│  ├─ data_dictionary.md
│  └─ powerbi_dashboard_guide.md
├─ erp_platform.pbix
├─ ingestion
│  ├─ connectors
│  │  ├─ excel_connector.py
│  │  └─ __init__.py
│  ├─ core
│  │  ├─ config_loader.py
│  │  ├─ loader.py
│  │  ├─ validator.py
│  │  └─ __init__.py
│  ├─ main.py
│  └─ __init__.py
├─ ml
│  ├─ demand_forecast
│  │  ├─ config.yaml
│  │  ├─ forecast.py
│  │  └─ __init__.py
│  ├─ schema_mapper
│  │  ├─ infer_mapping.py
│  │  ├─ ollama_client.py
│  │  ├─ schema_ventes_achats.yaml
│  │  └─ __init__.py
│  └─ __init__.py
├─ README.md
├─ Recap_Traitement_Donnees_ERP.pdf
├─ requirements.txt
└─ tests

```

