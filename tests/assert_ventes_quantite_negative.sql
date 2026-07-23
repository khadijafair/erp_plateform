select *
from {{ ref('fact_transactions') }}
where is_expedition_vente and quantite_stock > 0