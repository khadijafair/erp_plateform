select numero_article, count(*)
from {{ ref('stg_erp_referentiel_articles') }}
group by numero_article
having count(*) > 1