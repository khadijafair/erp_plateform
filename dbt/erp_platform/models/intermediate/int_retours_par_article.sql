{# Retours vente isolés : montant déjà négatif dans la convention du staging. #}

with retours as (

    select *
    from {{ ref('fact_transactions') }}
    where is_retour_vente

)

select
    article_key,
    count(*)                            as nb_lignes_retour,
    sum(montant_reel)                   as montant_total_retours  -- négatif

from retours
group by article_key
