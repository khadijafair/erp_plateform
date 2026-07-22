select
    numero_commande,
    numero_article       as article_matiere,
    sum(abs(quantite_normalisee)) as quantite_consommee
from {{ ref('stg_erp_production_assemblage') }}
where is_consommation
group by numero_commande, numero_article