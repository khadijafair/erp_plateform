# Dictionnaire de données — Source `erp_ventes_achats`

Basé sur l'analyse du fichier `Afficher_-_Écritures_comptables_article21.xlsx`
(71 588 lignes, période 2017-01-02 → 2019-12-31).

## Colonnes source → nom métier générique

| Colonne source (Excel) | Nom générique (pipeline) | Type | Observations |
|---|---|---|---|
| Date comptabilisation | `date_ecriture` | date | Aucune valeur manquante |
| Type écriture | `type_ecriture` | string | 2 valeurs : `Vente` (66 135), `Achat` (5 453) |
| Type document | `type_document` | string | 3 valeurs : `Expédition vente` (63 811), `Réception achat` (5 453), `Réception retour vente` (2 324) |
| N° document | `numero_document` | string | Identifiant du document comptable |
| Quantité | `quantite` | float | Convention de signe **négative** majoritaire (médiane -2) — à normaliser |
| N° article | `numero_article` | string | 353 articles uniques |
| Code unité | `code_unite` | string | 12 unités différentes (QUINTAL très majoritaire, UNITE, KG, LITRE, CRT-*, SAC, FARDEAU...) |
| Quantité facturée | `quantite_facturee` | float | Même problème de signe que `quantite` |
| Montant (réel) | `montant_reel` | float | Majoritairement positif |

## Points de vigilance identifiés (à traiter en couche métier / dbt)

1. **Signe des quantités inversé** : `quantite` et `quantite_facturee` sont majoritairement négatives alors que `montant_reel` est positif. Il faut documenter et normaliser cette convention avant tout calcul (marge, ABC, prévision).
2. **`Réception retour vente`** est classée sous `type_ecriture = Vente` mais représente une remise en cause d'une vente antérieure : elle doit être traitée à part (déduite du CA), pas additionnée aux ventes normales.
3. **Unités hétérogènes** : une `Quantité` de 300 ne représente pas la même chose en `QUINTAL` qu'en `UNITE` ou en `CRT-12*1`. Une table de conversion d'unités par article est nécessaire avant toute comparaison inter-articles.
4. **Doublons apparents sur la clé (`numero_document`, `numero_article`)** : 12 418 lignes concernées. À investiguer — probablement des lignes légitimes (un même article livré en plusieurs fois sur un même document) plutôt qu'une vraie erreur, mais à confirmer avec l'entreprise avant de fixer la règle de dédoublonnage définitive.
5. **Aucune colonne client identifiée** dans cet extrait — à redemander si une segmentation client (RFM) est souhaitée plus tard.

## Règle de mapping

Ce dictionnaire correspond au fichier `config/sources/erp_ventes_achats.yaml`.
Toute évolution du format source (renommage/réordonnancement de colonnes)
se traite en dupliquant ce fichier de config, jamais en modifiant le code Python.
