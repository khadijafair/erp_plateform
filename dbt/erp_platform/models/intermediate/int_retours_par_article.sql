with retours as (

    select *
    from {{ ref('fact_transactions') }}
    where is_retour_vente

)

select
    numero_article,
    count(*)                            as nb_lignes_retour,
    sum(montant_reel)                   as montant_total_retours

from retours
group by numero_article