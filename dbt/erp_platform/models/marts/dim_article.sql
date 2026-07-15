{#
  Dimension minimale : le fichier source ne contient aucun référentiel
  article (pas de famille, pas de désignation). On expose donc ce qu'on
  peut dériver des transactions elles-mêmes ; à enrichir plus tard si un
  référentiel article ERP devient disponible (table dédiée dans Dynamics).
#}

with transactions as (

    select * from {{ ref('stg_erp_ventes_achats') }}

),

par_article as (

    select
        numero_article,
        min(date_ecriture)                                     as premiere_transaction,
        max(date_ecriture)                                     as derniere_transaction,
        count(*)                                                as nb_lignes,
        count(*) filter (where type_ecriture = 'Vente')         as nb_lignes_vente,
        count(*) filter (where type_ecriture = 'Achat')         as nb_lignes_achat,
        count(*) filter (where is_retour_vente)                 as nb_lignes_retour,
        count(distinct code_unite)                              as nb_unites_distinctes,
        mode() within group (order by code_unite)               as unite_principale

    from transactions
    group by numero_article

)

select
    {{ dbt_utils.generate_surrogate_key(['numero_article']) }}  as article_key,
    numero_article,
    premiere_transaction,
    derniere_transaction,
    nb_lignes,
    nb_lignes_vente,
    nb_lignes_achat,
    nb_lignes_retour,
    unite_principale,
    nb_unites_distinctes > 1                                    as a_plusieurs_unites

from par_article
