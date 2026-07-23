-- Aucun article avec incohérence d'unité ne doit être marqué fiable, peu importe son CA
select *
from {{ ref('mart_marge_article') }}
where unite_vente_coherente_avec_production = false
  and marge_fiable = true