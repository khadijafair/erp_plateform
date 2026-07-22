select
    numero_article,
    description,
    unite_base,
    stock

from {{ source('raw', 'erp_referentiel_articles') }}