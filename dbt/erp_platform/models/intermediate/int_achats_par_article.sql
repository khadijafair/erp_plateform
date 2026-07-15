{#
  Coût Moyen Unitaire Pondéré (CMUP) par article, calculé sur l'ensemble
  de l'historique disponible (pas de FIFO/LIFO ici : on n'a pas l'info de
  quel lot d'achat correspond à quelle vente, donc le CMUP global est
  l'approximation la plus défendable avec les données disponibles).
#}

with achats as (

    select *
    from {{ ref('fact_transactions') }}
    where type_ecriture = 'Achat'

)

select
    article_key,

    count(*)                                       as nb_lignes_achat,
    sum(quantite_stock)                             as quantite_totale_achetee,
    sum(montant_reel)                               as montant_total_achat,

    -- CMUP : null si aucune quantité achetée (évite une division par zéro)
    case
        when sum(quantite_stock) > 0
            then round(sum(montant_reel) / sum(quantite_stock), 4)
        else null
    end                                              as cout_unitaire_moyen_pondere,

    min(date_id)                                    as premier_achat,
    max(date_id)                                    as dernier_achat

from achats
group by article_key
