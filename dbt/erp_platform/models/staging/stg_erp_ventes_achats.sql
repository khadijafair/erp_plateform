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

        -- Convention de signe unique pour tout le reste du pipeline :
        --   positif = entrée en stock (achat, retour client)
        --   négatif = sortie de stock (vente expédiée)
        -- Les valeurs sources sont déjà cohérentes avec cette convention
        -- dans >97% des cas ; on force via abs() plutôt que de garder le
        -- signe brut, pour absorber les quelques lignes de saisie inversée.
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

        -- Montant : on ne touche pas au signe des ventes (le retour vente
        -- est déjà quasi systématiquement négatif dans la source, ce qui
        -- est le comportement voulu pour un CA net). On force juste les
        -- achats en positif (coût), au cas où une ligne serait saisie
        -- en négatif par erreur.
        case
            when type_ecriture = 'Achat' then abs(montant_reel)
            else montant_reel
        end                                                 as montant_signe

    from renamed

),

-- Un même (numero_document, numero_article) peut légitimement apparaître
-- plusieurs fois (plusieurs lots/lignes sur le même bon de livraison).
-- Ce n'est PAS un doublon à dédupliquer : on construit donc une clé
-- technique sur l'ensemble des colonnes + un row_number, pour ne garder
-- qu'un identifiant stable, sans jamais supprimer de lignes réelles.
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

    -- indicateur utile pour le monitoring qualité (reprend le warning
    -- déjà émis par ingestion/core/validator.py), mais n'affecte plus
    -- la clé technique de la ligne
    count(*) over (
        partition by numero_document, numero_article
    ) > 1                                                   as cle_metier_non_unique

from avec_cle