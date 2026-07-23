{#
  CMUP par article, calculé depuis le staging (pas depuis le mart).
  Pas de FIFO/LIFO : on n'a pas l'info de lot.
#}

with achats as (

    select *
    from {{ ref('stg_erp_ventes_achats') }}
    where type_ecriture = 'Achat'

)

select
    numero_article,

    count(*)                                       as nb_lignes_achat,
    sum(quantite_stock)                            as quantite_totale_achetee,
    sum(montant_reel)                              as montant_total_achat,

    case
        when sum(quantite_stock) > 0
            then round(sum(montant_reel) / sum(quantite_stock), 4)
        else null
    end                                            as cout_unitaire_moyen_pondere,

    min(date_ecriture)                             as premier_achat,
    max(date_ecriture)                             as dernier_achat

from achats
group by numero_article