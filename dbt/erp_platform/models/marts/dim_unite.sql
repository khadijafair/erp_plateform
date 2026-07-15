{#
  Les unités observées dans les données sont hétérogènes et non
  convertibles entre elles sans référentiel externe (1 QUINTAL = 100 kg
  est une conversion standard qu'on peut coder en dur, mais les unités de
  conditionnement type CRT-12*1 dépendent du produit et ne sont PAS
  convertibles ici sans table de correspondance article -> poids/carton,
  qui n'existe pas dans le fichier source). On se contente donc de
  catégoriser, sans convertir.
#}

with unites as (

    select distinct code_unite
    from {{ ref('stg_erp_ventes_achats') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['code_unite']) }}     as unite_key,
    code_unite,

    case
        when code_unite in ('QUINTAL', 'KG')        then 'poids'
        when code_unite in ('UNITE', 'LITRE')       then 'unitaire'
        when code_unite like 'CRT-%'                then 'conditionnement_carton'
        when code_unite in ('SAC', 'FARDEAU')       then 'conditionnement_sac_fardeau'
        else 'non_classe'
    end                                                        as categorie_unite,

    case
        when code_unite = 'QUINTAL' then 1000.0
        when code_unite = 'KG'      then 1.0
        else null
    end                                                        as equivalent_kg_si_poids

from unites
