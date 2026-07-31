with transactions as (
    select * from {{ ref('stg_erp_ventes_achats') }}
),

par_article as (
    select
        numero_article,
        min(date_ecriture) as premiere_transaction,
        max(date_ecriture) as derniere_transaction,
        count(*) as nb_lignes,
        count(*) filter (where is_expedition_vente) as nb_lignes_vente,
        count(*) filter (where is_retour_vente) as nb_lignes_retour,
        count(distinct code_unite) as nb_unites_distinctes,
        mode() within group (order by code_unite) as unite_principale
    from transactions
    group by numero_article
),

ref_articles as (
    select * from {{ ref('stg_erp_referentiel_articles') }}
),

production as (
    select
        numero_article,
        count(distinct code_unite) as nb_unites_production,
        mode() within group (order by code_unite) as unite_production_principale
    from {{ ref('stg_erp_production_assemblage') }}
    where is_resultat
    group by numero_article
)

select
    {{ dbt_utils.generate_surrogate_key(['p.numero_article']) }} as article_key,
    p.numero_article,
    r.description as description_article,
    p.unite_principale,
    p.nb_unites_distinctes > 1 as a_plusieurs_unites,
    pr.unite_production_principale,
    (p.unite_principale = pr.unite_production_principale) as unite_vente_coherente_avec_production,
    case 
        when p.unite_principale like 'QUINTAL%' and (pr.unite_production_principale like 'CRT-%' or pr.unite_production_principale = 'CARTON') 
            then 'Vente en QUINTAL mais Production en CARTON'
        else null
    end as type_incoherence
from par_article p
left join ref_articles r on p.numero_article = r.numero_article
left join production pr on p.numero_article = pr.numero_article