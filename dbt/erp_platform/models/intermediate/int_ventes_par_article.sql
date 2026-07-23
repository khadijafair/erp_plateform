{#
  Agrégation des ventes par article (retours exclus via is_expedition_vente).
  Les retours sont traités séparément dans int_retours_par_article.
#}

with ventes as (

    select *
    from {{ ref('stg_erp_ventes_achats') }}
    where is_expedition_vente

)

select
    numero_article,

    count(*)                                       as nb_lignes_vente,
    sum(abs(quantite_stock))                        as quantite_totale_vendue,
    sum(montant_reel)                              as chiffre_affaires,

    case
        when sum(abs(quantite_stock)) > 0
            then round(sum(montant_reel) / sum(abs(quantite_stock)), 4)
        else null
    end                                            as prix_unitaire_moyen_vente,

    min(date_ecriture)                             as premiere_vente,
    max(date_ecriture)                             as derniere_vente

from ventes
group by numero_article