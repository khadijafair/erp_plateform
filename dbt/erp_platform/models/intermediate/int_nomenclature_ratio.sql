{#
  Ratio de consommation matière par unité de produit fini, calculé sur
  l'ensemble des commandes observées (ratio pondéré global : somme des
  consommations / somme des productions, pas une moyenne des ratios par
  commande — plus robuste face aux petites commandes qui fausseraient
  une moyenne simple).

  Limite assumée : si un numero_commande produit PLUSIEURS articles finis
  différents à la fois, ce modèle attribue la totalité des consommations de
  cette commande à chacun d'eux (impossible de départager sans info
  supplémentaire) — voir la colonne commande_multi_produits pour repérer
  ces cas et interpréter leur ratio avec prudence plutôt que les cacher.
#}

with resultats as (
    select * from {{ ref('int_resultats_assemblage') }}
),

consommations as (
    select * from {{ ref('int_consommations_assemblage') }}
),

nb_produits_par_commande as (
    select numero_commande, count(distinct article_fini) as nb_articles_finis
    from resultats
    group by numero_commande
),

paires as (

    select
        r.article_fini,
        c.article_matiere,
        r.numero_commande,
        r.quantite_produite,
        c.quantite_consommee,
        (npc.nb_articles_finis > 1)   as commande_multi_produits

    from resultats r
    join consommations c on r.numero_commande = c.numero_commande
    join nb_produits_par_commande npc on r.numero_commande = npc.numero_commande

)

select
    article_fini,
    article_matiere,

    count(distinct numero_commande)                                    as nb_commandes_observees,
    sum(quantite_consommee)                                            as quantite_matiere_totale,
    sum(quantite_produite)                                             as quantite_produit_fini_totale,

    round(sum(quantite_consommee) / nullif(sum(quantite_produite), 0), 6)
                                                                        as ratio_consommation_par_unite,

    bool_or(commande_multi_produits)                                   as contient_commande_multi_produits

from paires
group by article_fini, article_matiere