select *
from {{ ref('fact_transactions') }}
where type_ecriture = 'Achat' and montant_reel < 0