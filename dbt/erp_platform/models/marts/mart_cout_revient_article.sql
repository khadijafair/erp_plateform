{#
  Coût de revient estimé d'un produit fini = somme, pour chaque matière
  première de sa nomenclature, de (ratio de consommation × coût moyen
  pondéré d'achat de cette matière).

  toutes_matieres_ont_cout_achat = false si au moins une matière première
  de la nomenclature n'a jamais été achetée dans les données Ventes/Achats
  (donc pas de CMUP connu) — le coût de revient serait alors sous-estimé,
  affiché quand même mais à ne pas publier comme fiable tel quel.
#}

with nomenclature as (
    select * from {{ ref('int_nomenclature_ratio') }}
),

achats as (
    select * from {{ ref('int_achats_par_article') }}
),

lignes as (

    select
        n.article_fini,
        n.article_matiere,
        n.ratio_consommation_par_unite,
        n.contient_commande_multi_produits,
        a.cout_unitaire_moyen_pondere                                          as cout_unitaire_matiere,
        (n.ratio_consommation_par_unite * a.cout_unitaire_moyen_pondere)       as cout_matiere_par_unite_produit

    from nomenclature n
    left join achats a
        on {{ dbt_utils.generate_surrogate_key(['n.article_matiere']) }} = a.article_key

)

select
    article_fini,

    count(*)                                          as nb_matieres_premieres,
    sum(cout_matiere_par_unite_produit)                as cout_revient_estime,
    bool_or(contient_commande_multi_produits)          as contient_commande_multi_produits,
    bool_and(cout_unitaire_matiere is not null)        as toutes_matieres_ont_cout_achat

from lignes
group by article_fini