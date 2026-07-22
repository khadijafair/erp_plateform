{#
  Staging = 1ère couche métier. On ne fait ici QUE de la fiabilisation :
    - typage / trim
    - normalisation du signe des quantités (convention stock unique)
    - identification des retours vente
    - clé technique stable, même pour les lignes multiples d'un même
      document/article (voir note plus bas)
  Aucun calcul de marge ici : ça viendra dans un mart dédié une fois
  fact_transactions disponible.
#}

{% set retours = var('retour_vente_document_types') %}
{% set ventes = var('vente_document_types') %}

with source as (

    select * from {{ source('raw', 'erp_ventes_achats') }}

),

renamed as (

    select
        date_ecriture::date                as date_ecriture,
        trim(type_ecriture)                as type_ecriture,
        trim(type_document)                as type_document,
        trim(numero_document)              as numero_document,
        trim(numero_article)               as numero_article,
        trim(code_unite)                   as code_unite,
        quantite::numeric                  as quantite_brute,
        quantite_facturee::numeric         as quantite_facturee_brute,
        montant_reel::numeric              as montant_reel

    from source

),

enrichi as (

    select
        *,

        type_document in (
            {% for t in retours %}'{{ t }}'{{ ", " if not loop.last }}{% endfor %}
        )                                                   as is_retour_vente,

        type_document in (
            {% for t in ventes %}'{{ t }}'{{ ", " if not loop.last }}{% endfor %}
        )                                                   as is_expedition_vente,

        -- Facteur de conversion (ex: CRT-12*1 -> 12)
        {{ get_conversion_factor('code_unite') }}           as conversion_factor,

        -- Quantité signée, PAS de conversion d'unité ici 
        case
            when type_document in ({% for t in ventes %}'{{ t }}'{{ ", " if not loop.last }}{% endfor %})
                then -abs(quantite_brute)
            else abs(quantite_brute)
        end                                                 as quantite_stock,

        case
            when type_document in ({% for t in ventes %}'{{ t }}'{{ ", " if not loop.last }}{% endfor %})
                then -abs(quantite_facturee_brute)
            else abs(quantite_facturee_brute)
        end                                                 as quantite_facturee_signee, 

        case
            when type_ecriture = 'Achat' then abs(montant_reel)
            else montant_reel
        end                                                    as montant_signe

    from renamed

),

avec_cle as (

    select
        *,
        row_number() over (
            partition by
                date_ecriture, type_ecriture, type_document, numero_document,
                numero_article, code_unite, quantite_brute,
                quantite_facturee_brute, montant_reel
            order by (select 1)
        )                                                   as occurrence_ligne

    from enrichi

)

select
    {{ dbt_utils.generate_surrogate_key([
        'date_ecriture', 'type_ecriture', 'type_document', 'numero_document',
        'numero_article', 'code_unite', 'quantite_brute',
        'quantite_facturee_brute', 'montant_reel', 'occurrence_ligne'
    ]) }}                                                   as transaction_id,

    date_ecriture,
    type_ecriture,
    type_document,
    numero_document,
    numero_article,
    code_unite,
    is_retour_vente,
    is_expedition_vente,
    quantite_stock,
    quantite_facturee_signee,
    montant_signe as montant_reel,                                         

    -- indicateur utile pour le monitoring qualité
    count(*) over (
        partition by numero_document, numero_article
    ) > 1                                                   as cle_metier_non_unique

from avec_cle