# Contexte du projet — à lire avant toute intervention

Ce document résume l'état complet du projet pour permettre à n'importe quel
assistant IA (ou à moi dans une nouvelle conversation) de reprendre le travail
sans perdre le contexte ni refaire les erreurs déjà corrigées.

**Colle ce fichier en entier au début d'une nouvelle conversation**, avant de
poser ta question, pour que l'assistant ait tout le contexte nécessaire.

---

## 1. Contexte général

- **Projet** : stage d'ingénierie IT (Maroc), sujet "pipeline de données ERP".
- **Objectif** : plateforme Data Engineering + Analytics Engineering + ML,
  construite comme un vrai projet valorisable sur un CV d'ingénieur (Maroc,
  France, Allemagne), pas un simple exercice.
- **Deadline** : soutenance début septembre (viser le 5 septembre).
- **Données** : extraits réels de l'ERP Microsoft Dynamics d'une entreprise
  agroalimentaire (ventes, achats, production/assemblage, référentiel articles).
- **Personne** : ingénieure junior, apprend en marchant, préfère des
  explications claires et des vérifications concrètes avant de faire confiance
  à un résultat. Attention au budget de tokens — rester efficace, ne pas
  ré-expliquer ce qui est déjà su.

---

## 2. Architecture technique

```
Excel (ERP) → Ingestion Python (config-driven) → PostgreSQL (raw)
    → dbt (staging → intermediate → marts) → ML Python (Prophet)
    → Power BI (dashboards)
```

**Principe non négociable** : séparation stricte entre une **couche générique**
(ne connaît rien du métier — ingestion, validation de schéma, chargement) et
des **modules métier** (règles spécifiques au domaine Ventes/Achats/Production).
Aucun nom de colonne du fichier source n'est écrit en dur dans le code Python —
tout passe par des fichiers YAML de configuration (`config/sources/*.yaml`).

### Stack
Python (pandas, SQLAlchemy) · PostgreSQL · dbt (+ dbt_utils) · Prophet
(Scikit-Learn en perspective) · Power BI · Ollama (LLM local, assistance à
l'ajout de nouvelles sources) · Docker (partiel) · n8n (pas encore fait) ·
Prometheus/Grafana (pas encore fait)

### Structure des dossiers du repo
```
erp-platform/
├── config/sources/*.yaml       # mapping + schéma par source (Ventes/Achats, Production, Référentiel)
├── ingestion/                  # connecteur Excel générique, validation, chargement
├── dbt/erp_platform/
│   ├── seeds/unite_conversion.csv   # conversions d'unités, avec colonne valide_par_entreprise
│   └── models/
│       ├── staging/            # stg_erp_ventes_achats, stg_erp_production_assemblage, stg_erp_referentiel_articles
│       ├── intermediate/       # agrégations (int_achats_par_article, int_nomenclature_ratio, etc.)
│       └── marts/              # fact_transactions, dim_*, mart_marge_article, mart_abc_article, mart_anomalies_ventes, mart_cout_revient_article
├── ml/
│   ├── demand_forecast/        # Prophet, prévision 8 semaines, articles classe A
│   └── schema_mapper/          # Ollama : propose un mapping YAML pour une nouvelle source (brouillon à valider, jamais utilisé au runtime)
└── docs/                       # dictionnaire de données, guide Power BI
```

---

## 3. État d'avancement (feuille de route)

- [x] Ingestion générique + validation de schéma — testé sur 71 588 lignes réelles
- [x] Modélisation dbt (staging/marts), schéma en étoile — tests dbt en place
- [x] Sources supplémentaires ajoutées : Production/Assemblage (39 047 lignes),
      Référentiel Articles (183 lignes)
- [x] Calcul de marge via nomenclature (BOM) — voir section 5 pour la méthode et ses limites
- [x] Classement ABC/Pareto, détection d'anomalies (ventes à perte)
- [x] Prévision de la demande (Prophet, 8 semaines, articles classe A)
- [x] Dashboards Power BI (5 pages : vue d'ensemble, marge, ABC, anomalies, prévision)
- [x] Module Ollama pour proposer un mapping de colonnes sur une nouvelle source (2 modes : schéma cible connu / bootstrap nouveau domaine)
- [ ] **Orchestration n8n** — prochaine étape officielle
- [ ] Monitoring Prometheus/Grafana sur le pipeline
- [ ] Plateforme collaborative (upload non-IT → mapping IA → validation IT)
- [ ] Preuve de généricité sur un 2ᵉ domaine (RH/produits)
- [ ] Saisonnalité (Ramadan, Aïd...) dans Prophet — actuellement seulement `yearly_seasonality=True`, jamais vérifié ni enrichi d'événements métier
- [ ] Docker-compose complet (aujourd'hui seul Postgres est conteneurisé, pas le pipeline entier)
- [ ] CI/CD léger (GitHub Actions relance `dbt test`)
- [ ] Repo GitHub public : https://github.com/khadijafair/erp_plateform (déjà en ligne)

---

## 4. Conventions et décisions clés (à respecter, ne pas re-décider)

- **`quantite_stock`** (dans `fact_transactions`) : signe normalisé (négatif =
  vente/sortie, positif = achat/entrée), **PAS de conversion d'unité
  appliquée** — utilisé tel quel par le forecast Prophet et Power BI page 5.
  Ne jamais y appliquer de facteur de conversion sans revalider ces deux usages.
- **`montant_reel`** : normalisé pour que les achats soient toujours positifs
  (`montant_signe` dans le staging). Vérifier régulièrement :
  `SELECT count(*) FROM fact_transactions WHERE type_ecriture='Achat' AND montant_reel<0` → doit être **0**.
- **Conversions d'unité** : passent exclusivement par le seed
  `unite_conversion.csv`, avec colonne `valide_par_entreprise`. Seul
  `QUINTAL = 1000 kg` est confirmé par l'entreprise à ce jour. **Ne jamais**
  utiliser de facteurs inventés (macro `get_conversion_factor` a été
  partiellement supprimée/corrigée pour cette raison — vérifier qu'elle n'est
  plus utilisée sur `quantite_stock`).
- **Doublons de documents** (`numero_document` + `numero_article` répétés) :
  légitimes (plusieurs lots sur un même bon de livraison), **ne jamais
  dédupliquer** — juste signalés via `cle_metier_non_unique`.
- **Mode de chargement (`ingestion/core/loader.py`)** : `append` par défaut
  (historique cumulatif — Ventes/Achats, Production). `replace` uniquement
  pour les référentiels/master data (`erp_referentiel_articles`) via
  `business_rules.mode_chargement: replace` dans la config YAML. **Piège
  fréquent** : relancer 2 fois l'ingestion d'une source en `append` double
  silencieusement les lignes — toujours vérifier `count(*)` après ingestion.
- **Ollama** : utilisé UNIQUEMENT pour proposer un brouillon de mapping au
  moment d'ajouter une nouvelle source. Le pipeline d'ingestion/dbt ne
  l'appelle jamais au runtime — tout reste déterministe et testable.

---

## 5. Méthode de calcul de la marge (importante, complexe, déjà débuggée plusieurs fois)

Deux méthodes en cascade dans `mart_marge_article` :
1. **Nomenclature** (prioritaire) : coût de revient via `mart_cout_revient_article`,
   qui remonte du produit fini vendu → sa recette de fabrication
   (`int_nomenclature_ratio`, construite depuis `erp_production_assemblage`)
   → coût des matières premières consommées (CMUP achat).
2. **Achat direct** (repli) : pour les articles achetés ET revendus sous le
   même `numero_article` (négoce, sans transformation).

`marge_fiable = true` seulement si : coût calculable, article réellement
vendu, une seule unité de mesure utilisée, pas de commande de production
multi-produits ambiguë, toutes les matières premières ont un coût d'achat
connu. **Ne jamais** ajouter d'exception basée sur le chiffre d'affaires pour
forcer plus d'articles à être "fiables" — piège déjà rencontré et corrigé
(une exception `chiffre_affaires_net < 10000000` avait été ajoutée par erreur
pour "sauver" des gros articles, ça faussait tout : à ne jamais refaire).

**Chiffres de référence validés** (après correction de tous les bugs de
doublons) : CA total ventes ≈ 551M (unité monétaire ERP). Tableau croisé
classe ABC × marge_fiable à revérifier après tout changement dans cette
zone — méthode de vérification en section 6.

---

## 6. Méthode de vérification (à toujours appliquer avant de valider un résultat)

1. Lancer `dbt run` puis `dbt test` — doit toujours être 100% PASS.
2. Vérifier les volumes de lignes à chaque étape (`raw` → `staging` →
   `marts`) : aucune perte ni duplication inexpliquée.
3. Vérifier les règles métier connues avec des requêtes SQL ciblées (voir
   section 4 pour les invariants à tester : signe montant, signe quantité,
   doublons).
4. Repérer les valeurs extrêmes (`marge_pct > 100` ou `< -1000` etc.) et
   vérifier qu'elles sont bien exclues de `marge_fiable`, pas supprimées de
   la donnée brute.
5. Contrôler un article précis à la main (nomenclature, coûts) pour un vrai
   jugement métier, pas juste un test automatique.
6. Ne jamais valider un chiffre "parce qu'il a l'air propre" — chercher
   activement une explication de pourquoi il a changé après une modification.

---

## 7. Instructions pour l'assistant IA qui reprend ce projet

- Ne pas re-proposer les mêmes solutions déjà écartées (voir section 4).
- Toujours vérifier avec des requêtes SQL concrètes avant d'affirmer qu'un
  résultat est correct — la personne préfère qu'on doute et qu'on vérifie
  plutôt qu'on rassure sans preuve.
- Rester concis, elle fait attention à son budget de tokens.
- Ne jamais renvoyer un zip complet du projet si un seul fichier a changé —
  donner uniquement le fichier modifié.
- Si une requête ou un résultat semble bizarre, le dire clairement plutôt que
  de minimiser.
- Le repo GitHub est public mais l'assistant ne peut généralement accéder
  qu'à des liens de fichiers précis (`/blob/main/...`), pas à la vue
  arborescence (bloquée pour les robots) — demander les liens un par un si besoin.
