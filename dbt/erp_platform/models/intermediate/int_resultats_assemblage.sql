select
    numero_commande,
    numero_article    as article_fini,
    sum(quantite_normalisee) as quantite_produite
from {{ ref('stg_erp_production_assemblage') }}
where is_resultat
group by numero_commande, numero_article