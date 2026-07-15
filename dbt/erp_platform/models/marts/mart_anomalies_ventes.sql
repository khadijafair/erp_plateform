{#
  Détection par règle métier (pas encore de ML ici) : une ligne de vente
  est signalée si son prix unitaire facturé est inférieur au CMUP achat de
  l'article. Complémentaire à une détection ML (Isolation Forest, phase
  Python) qui captera des anomalies plus subtiles (prix inhabituels sans
  seuil fixe) ; celle-ci sert de première alerte simple et explicable.

  Restreint aux articles où marge_fiable = true (une seule unité) pour
  éviter les faux positifs dus à un CMUP mélangeant des unités différentes.
#}

with ventes as (

    select *
    from {{ ref('fact_transactions') }}
    where is_expedition_vente

),

cout_article as (

    select article_key, cout_unitaire_moyen_pondere, marge_fiable
    from {{ ref('mart_marge_article') }}
    where marge_fiable

),

lignes_avec_cout as (

    select
        v.transaction_id,
        v.date_id,
        v.numero_document,
        v.article_key,
        v.montant_reel,
        abs(v.quantite_stock)                                            as quantite_vendue,

        case
            when abs(v.quantite_stock) > 0
                then round(v.montant_reel / abs(v.quantite_stock), 4)
            else null
        end                                                               as prix_unitaire_ligne,

        c.cout_unitaire_moyen_pondere

    from ventes v
    inner join cout_article c on v.article_key = c.article_key

)

select
    *,
    round(cout_unitaire_moyen_pondere - prix_unitaire_ligne, 4)          as perte_unitaire_estimee,
    round((cout_unitaire_moyen_pondere - prix_unitaire_ligne) * quantite_vendue, 2)
                                                                          as perte_totale_estimee

from lignes_avec_cout
where prix_unitaire_ligne < cout_unitaire_moyen_pondere
order by perte_totale_estimee desc
