# ERP Platform — Pipeline Data & ML End-to-End

Plateforme de données agnostique et pilotée par la configuration, construite sur des extraits réels de l'ERP Microsoft Dynamics d'une entreprise agroalimentaire.

> **Principe absolu** : aucun nom de colonne source n'est écrit en dur dans le code Python ou SQL. Tout passe par des fichiers YAML de mapping, rendant l'ingestion reproductible sur n'importe quel nouveau flux.

---

## 🏗️ Architecture

```
Excel (ERP) → Ingestion Python (config-driven) → PostgreSQL (raw)
    → dbt (staging → intermediate → marts) → ML Python (Prophet)
    → Power BI (dashboards)
```

| Couche | Technologie | Rôle |
|---|---|---|
| **Ingestion** | Python, pandas, SQLAlchemy | Connecteur Excel générique, validation de schéma, chargement vers PostgreSQL |
| **Stockage** | PostgreSQL 16 | Data Warehouse local, schémas isolés (`raw`, `staging`, `marts`, `ml`) |
| **Transformation** | dbt + dbt_utils | Modèle en étoile, classification ABC, détection d'anomalies |
| **Machine Learning** | Prophet (Meta), Ollama (Llama 3.1) | Prévision de la demande hebdomadaire, assistant IA de mapping YAML |
| **Restitution** | Power BI | Dashboards 5 pages : vue d'ensemble, ABC, prévisions, traçabilité production |
| **Orchestration** | Script Python natif (`pipeline.py`) | Pipeline complet exécutable sans dépendance externe (backup n8n) |

---

## 🚀 Démarrage rapide

### Prérequis
- Python 3.11+
- Docker & Docker Compose
- Git

### 1. Cloner et installer

```bash
git clone https://github.com/khadijafair/erp_plateform.git
cd erp_plateform
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Lancer l'infrastructure

```bash
docker compose up -d postgres adminer
```

### 3. Configurer dbt

```bash
cp dbt/profiles.yml.example dbt/profiles.yml
# Adapter les credentials si nécessaire (localhost par défaut)
```

### 4. Exécuter le pipeline complet

```bash
python pipeline.py
```

Cela exécute automatiquement :
- Ingestion des 3 sources (Ventes, Production, Référentiel Articles)
- `dbt seed && dbt run && dbt test`
- Prévisions Prophet sur les articles classe A

---

## 📊 Données traitées

| Source | Lignes | Description |
|---|---|---|
| Ventes | 65 053 | Écritures de vente (expéditions, retours) |
| Production / Assemblage | ~39 000 | Consommations matières premières et résultats d'assemblage |
| Référentiel Articles | 183 | Master data (description, unité, stock) |

---

## 📸 Dashboards Power BI

### Vue d'ensemble
![Vue d'ensemble](docs/screenshots/01_vue_ensemble.png)

### Marge et rentabilité
![Marge](docs/screenshots/02_marge.png)

### Classification ABC (Pareto)
![ABC](docs/screenshots/03_abc.png)

### Détection d'anomalies
![Anomalies](docs/screenshots/04_anomalies.png)

### Prévisions de demande (Prophet)
![Prévisions](docs/screenshots/05_previsions.png)

---

## 🧪 Qualité de données

- **47+ tests dbt** automatisés (`unique`, `not_null`, `relationships`, `accepted_values`)
- Validation de schéma à l'ingestion (types, valeurs autorisées, clés métier)
- Traçabilité complète (`_source_id`, `_source_file`, `_ingested_at`)
- Détection d'outliers dans les séries temporelles (IQR) avant prévision ML

---

## 🤖 Intelligence Artificielle (100 % local)

- **Ollama + Llama 3.1:8b** : génère un brouillon de mapping YAML pour toute nouvelle source Excel. Mode *schéma cible connu* ou *bootstrap* nouveau domaine. Le pipeline d'ingestion ne l'appelle jamais au runtime — tout reste déterministe et testable.
- **Prophet** : prévision de la demande à 8 semaines, articles classe A uniquement, avec prise en compte de la saisonnalité culturelle marocaine (Ramadan, Aïd, fêtes nationales) via régresseurs exogènes.

---

## 📁 Structure du repo

```
erp_plateform/
├── config/sources/           # Mapping YAML par source (généricité absolue)
├── ingestion/                # Connecteur Excel, validation, loader
├── dbt/erp_platform/
│   ├── models/               # staging / intermediate / marts
│   ├── seeds/                # Conversions d'unité validées par l'entreprise
│   └── macros/
├── ml/
│   ├── demand_forecast/      # Prophet + calendrier événements marocains
│   ├── production_forecast/  # Prophet 
│   └── schema_mapper/        # Ollama (assistant IA)
├── docker/                   # Grafana, Prometheus
├── docs/                     # Dictionnaire de données, guide Power BI, captures
└── pipeline.py               # Orchestration complète (backup n8n)
```

---

## 🗺️ Roadmap

- [x] Ingestion générique & validation (aucun nom de colonne en dur)
- [x] Modélisation dbt (schéma en étoile, 47+ tests)
- [x] Intégration Production + Référentiel Articles
- [x] Classification ABC/Pareto
- [x] Prévisions Prophet (8 semaines, saisonnalité culturelle)
- [x] Dashboards Power BI (5 pages)
- [x] Assistant IA de mapping (Ollama, RGPD-compliant)
- [x] Pipeline d'orchestration natif
- [ ] Calcul de marge et coût de revient (nécessite une source d'achat alignée temporellement — le modèle est structuré pour l'accueillir)
- [ ] Orchestration n8n
- [ ] Monitoring Prometheus/Grafana
- [ ] Plateforme collaborative (upload non-IT → IA → validation IT)

---

## 👤 Auteur

**Khadija Fair** — Stage d'ingénierie IT, Maroc.


