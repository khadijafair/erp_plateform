# Dashboards Power BI — guide de construction

Ce guide explique comment connecter Power BI Desktop à la base déjà construite
(ingestion + dbt + prévisions) et bâtir les dashboards. Rien à coder : tout se
fait dans l'interface Power BI, ce document sert de plan à suivre pas à pas.

## 1. Connexion à la base

1. Power BI Desktop → **Obtenir les données** → **Base de données PostgreSQL**
2. Serveur : `localhost:5432` — Base de données : `erp_platform`
3. Mode : **Import** (pas DirectQuery — le volume est petit, l'import est plus rapide à l'usage et permet de travailler hors connexion)
4. Identifiants : ceux de ton `.env` (utilisateur `postgres` / mot de passe défini)
5. Dans le navigateur, sélectionne dans le schéma **`public_marts`** (ou le nom que tu as identifié chez toi) :
   - `fact_transactions`
   - `dim_article`, `dim_date`, `dim_unite`
   - `mart_marge_article`
   - `mart_abc_article`
   - `mart_anomalies_ventes`

   Et dans le schéma **`ml`** :
   - `previsions_demande_hebdo`
6. **Charger**

## 2. Modèle de données (onglet Modèle)

Vérifie/crée ces relations (Power BI les détecte souvent automatiquement, à confirmer) :

| Table 1 | Colonne | Table 2 | Colonne | Cardinalité |
|---|---|---|---|---|
| fact_transactions | article_key | dim_article | article_key | plusieurs-à-1 |
| fact_transactions | date_id | dim_date | date_id | plusieurs-à-1 |
| fact_transactions | unite_key | dim_unite | unite_key | plusieurs-à-1 |
| mart_marge_article | article_key | dim_article | article_key | 1-à-1 |
| mart_abc_article | article_key | dim_article | article_key | 1-à-1 |
| mart_anomalies_ventes | article_key | dim_article | article_key | plusieurs-à-1 |
| previsions_demande_hebdo | article_key | dim_article | article_key | plusieurs-à-1 |

**Ne relie pas** `previsions_demande_hebdo.semaine` à `dim_date` : les semaines prévues (futures) n'existent pas dans `dim_date`, qui ne couvre que l'historique. Laisse `semaine` comme un axe de date indépendant sur les visuels de prévision.

## 3. Mesures DAX à créer

Nouvelle mesure (clic droit sur `fact_transactions` → *Nouvelle mesure*) pour chacune :

```dax
CA Net Total = CALCULATE(SUM(fact_transactions[montant_reel]), fact_transactions[type_ecriture] = "Vente")

Achats Total = CALCULATE(SUM(fact_transactions[montant_reel]), fact_transactions[type_ecriture] = "Achat")

Marge Totale Fiable = CALCULATE(SUM(mart_marge_article[marge_estimee]), mart_marge_article[marge_fiable] = TRUE())

Nb Articles Marge Fiable = CALCULATE(COUNTROWS(mart_marge_article), mart_marge_article[marge_fiable] = TRUE())

Nb Ventes A Perte = COUNTROWS(mart_anomalies_ventes)

Perte Totale Estimee = SUM(mart_anomalies_ventes[perte_totale_estimee])

CA Classe A = CALCULATE(SUM(mart_abc_article[chiffre_affaires_net]), mart_abc_article[classe_abc] = "A")

Pct CA Classe A = DIVIDE([CA Classe A], SUM(mart_abc_article[chiffre_affaires_net]))
```

## 4. Page 1 — Vue d'ensemble

- 4 cartes KPI : **CA Net Total**, **Marge Totale Fiable**, **Nb Ventes A Perte**, **Perte Totale Estimee**
- Graphique en courbes : CA net par mois (axe = `dim_date[annee]`/`dim_date[mois]`, valeur = `[CA Net Total]`)
- Graphique en barres : CA net par `dim_article[unite_principale]` ou par mois, selon ce qui est le plus lisible
- Zone de texte : *"Marge calculée sur X articles sur 353 — voir page Marge pour le détail"* (référence directe à la limite qu'on a documentée)

## 5. Page 2 — Marge & rentabilité

- Tableau : `mart_marge_article` filtré sur `marge_fiable = TRUE`, colonnes `numero_article`, `chiffre_affaires_net`, `cout_estime_vendu`, `marge_estimee`, `marge_pct`
- Graphique en barres : `marge_pct` par `numero_article`, trié décroissant
- Carte : **Nb Articles Marge Fiable** (16 / 353 — affiche honnêtement la couverture)
- Zone de texte expliquant la limite (produits finis vs matières premières, cf. README du projet)

## 6. Page 3 — Analyse ABC (Pareto)

- Graphique combiné (barres + courbe) : barres = `chiffre_affaires_net` par article (triés décroissant), courbe = `pct_cumule_ca`
- Anneau (donut) : répartition du CA par `classe_abc` (A/B/C)
- Carte : **Pct CA Classe A** (doit avoisiner 80%, cf. logique Pareto)

## 7. Page 4 — Anomalies (ventes à perte)

- Tableau : `mart_anomalies_ventes` trié par `perte_totale_estimee` décroissant, colonnes `numero_document`, `date_id`, `numero_article` (via relation), `prix_unitaire_ligne`, `cout_unitaire_moyen_pondere`, `perte_totale_estimee`
- Carte : **Nb Ventes A Perte** et **Perte Totale Estimee**
- Graphique en barres : perte totale par mois (relie `date_id` → `dim_date`)

## 8. Page 5 — Prévision de la demande

Cette page combine historique réel + prévision, ce qui nécessite un petit assemblage en **Power Query** (pas de code, juste des clics) :

1. **Accueil → Transformer les données** (ouvre Power Query)
2. Dupliquer la requête `fact_transactions` → renommer `Demande Historique`
3. Filtrer sur `is_expedition_vente = TRUE` et sur les article_key des classes A
4. **Regrouper par** : `article_key`, `numero_article`, semaine (colonne calculée `Date.StartOfWeek([date_ecriture])`) → agrégation `Sum` de `quantite_stock` (en valeur absolue)
5. Ajouter une colonne `Type = "Historique"`
6. Sur la requête `previsions_demande_hebdo` : garder `article_key`, `numero_article`, `semaine`, `quantite_prevue` (renommer en `quantite`), ajouter colonne `Type = "Prévision"`
7. **Accueil → Ajouter des requêtes** → fusionner `Demande Historique` + `previsions_demande_hebdo` en une seule table `Demande Combinee`
8. Fermer et appliquer

Puis sur la page :
- Filtre/segment : liste déroulante `numero_article` (un seul article affiché à la fois, plus lisible)
- Graphique en courbes : axe = `semaine`, valeur = `quantite`, **légende = `Type`** (2 courbes distinctes : Historique en une couleur, Prévision en une autre, avec la rupture visible fin décembre 2019)
- Optionnel : ajouter `quantite_prevue_min`/`quantite_prevue_max` en zone ombrée (bande d'incertitude) via un graphique en aires

## 9. Avant de présenter à ton encadrant

- Vérifie que le **mode Import a bien rafraîchi** (bouton *Actualiser*) après ton dernier `dbt run` / `python -m ml.demand_forecast.forecast`
- Renomme les tables/mesures dans le volet Champs si les noms techniques (`mart_marge_article`) sont peu lisibles pour un public non technique — Power BI permet de les renommer sans toucher à la base
- Enregistre en `.pbix` et garde-le dans le repo (hors `.gitignore`, contrairement aux données) pour que l'entreprise puisse le rouvrir après ton stage
