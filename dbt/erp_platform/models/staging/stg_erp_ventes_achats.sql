{#
  Staging Ventes 2023-2024.
  Filtre : uniquement type_ecriture = 'Vente' 
#}

with source as (

    select * from {{ source('raw', 'erp_ventes_achats') }}
    where type_ecriture = 'Vente'

),

renamed as (

    select
        date_ecriture::date                as date_ecriture,
        trim(type_ecriture)                as type_ecriture,
        trim(type_document)                as type_document,
        NULL::varchar                      as numero_document,  -- absent de la source
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

        -- Détection heuristique des retours (à adapter selon les valeurs réelles)
        lower(type_document) like '%retour%' as is_retour_vente,

        -- Toutes les lignes restantes sont des ventes
        true                               as is_expedition_vente,

        -- Convention stock : vente = sortie = négatif
        -abs(quantite_brute)               as quantite_stock,

        -abs(quantite_facturee_brute)      as quantite_facturee_signee,

        -- Montant au signe d'origine
        montant_reel                       as montant_signe

    from renamed

),

avec_cle as (

    select
        *,
        row_number() over (
            partition by
                date_ecriture, type_ecriture, type_document, numero_article,
                code_unite, quantite_brute, quantite_facturee_brute, montant_reel
            order by numero_article, quantite_brute
        )                                                   as occurrence_ligne

    from enrichi

)

select
    {{ dbt_utils.generate_surrogate_key([
        'date_ecriture', 'type_ecriture', 'type_document', 'numero_article',
        'code_unite', 'quantite_brute', 'quantite_facturee_brute',
        'montant_reel', 'occurrence_ligne'
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

    -- Pas de cle_metier_non_unique sans numero_document
    false                                                   as cle_metier_non_unique,

    occurrence_ligne

from avec_cle