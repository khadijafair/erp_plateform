with source as (

    select * from {{ source('raw', 'erp_production_assemblage') }}

),

renamed as (

    select
        trim(numero_origine)               as numero_origine,
        date_ecriture::date                as date_ecriture,
        trim(type_ecriture)                as type_ecriture,
        trim(numero_commande)              as numero_commande,
        trim(type_document)                as type_document,
        trim(numero_document)              as numero_document,
        quantite::numeric                  as quantite,
        trim(numero_article)               as numero_article,
        trim(code_magasin)                 as code_magasin,
        trim(code_unite)                   as code_unite

    from source

),

enrichi as (

    select
        renamed.*,
        renamed.type_ecriture = 'Consommation d''assemblage'    as is_consommation,
        renamed.type_ecriture = 'Résultat d''assemblage'         as is_resultat,

        renamed.quantite * coalesce(
            case when uc.valide_par_entreprise = 'oui' then uc.facteur_vers_unite_reference end,
            1
        )                                                        as quantite_normalisee,

        (uc.valide_par_entreprise is distinct from 'oui')         as conversion_non_confirmee

    from renamed
    left join {{ ref('unite_conversion') }} uc on renamed.code_unite = uc.code_unite

),

avec_cle as (

    select
        *,
        row_number() over (
            partition by
                numero_origine, date_ecriture, type_ecriture, numero_commande,
                type_document, numero_document, quantite, numero_article,
                code_magasin, code_unite
            order by (select 1)
        )                                               as occurrence_ligne

    from enrichi

)

select
    {{ dbt_utils.generate_surrogate_key([
        'numero_origine', 'date_ecriture', 'type_ecriture', 'numero_commande',
        'type_document', 'numero_document', 'quantite', 'numero_article',
        'code_magasin', 'code_unite', 'occurrence_ligne'
    ]) }}                                               as production_id,

    numero_origine,
    date_ecriture,
    type_ecriture,
    is_consommation,
    is_resultat,
    numero_commande,
    type_document,
    numero_document,
    quantite,
    quantite_normalisee,
    conversion_non_confirmee,
    numero_article,
    code_magasin,
    code_unite,

    count(*) over (
        partition by numero_document, numero_article
    ) > 1                                               as cle_metier_non_unique

from avec_cle