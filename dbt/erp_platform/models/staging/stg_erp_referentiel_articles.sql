{#
  Staging du référentiel articles (master data).
  Nettoyage minimal : trim des codes, typage explicite.
#}

with source as (

    select * from {{ source('raw', 'erp_referentiel_articles') }}

),

renamed as (

    select
        trim(numero_article)               as numero_article,
        trim(description)                  as description,
        trim(unite_base)                   as unite_base,
        stock::numeric                     as stock

    from source

)

select
    {{ dbt_utils.generate_surrogate_key(['numero_article']) }} as article_id,

    numero_article,
    description,
    unite_base,
    stock

from renamed