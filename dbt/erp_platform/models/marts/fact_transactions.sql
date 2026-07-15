with transactions as (

    select * from {{ ref('stg_erp_ventes_achats') }}

),

dim_article as (

    select article_key, numero_article from {{ ref('dim_article') }}

),

dim_unite as (

    select unite_key, code_unite from {{ ref('dim_unite') }}

)

select
    t.transaction_id,
    t.date_ecriture                        as date_id,
    a.article_key,
    u.unite_key,

    t.type_ecriture,
    t.type_document,
    t.numero_document,
    t.is_retour_vente,
    t.is_expedition_vente,

    -- mesures
    t.quantite_stock,
    t.quantite_facturee_signee,
    t.montant_reel,

    t.cle_metier_non_unique

from transactions t
left join dim_article a on t.numero_article = a.numero_article
left join dim_unite u on t.code_unite = u.code_unite
