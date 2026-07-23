{#
  Marge brute ESTIMÉE par article = CA net - coût des quantités vendues.

  Méthodes par ordre de préférence :
    1. NOMENCLATURE : produit fini issu de l'atelier.
    2. ACHAT DIRECT : article revendu sans transformation.

  marge_fiable = true UNIQUEMENT si niveau_confiance = 'haute'.
#}

with ventes as (
    select * from {{ ref('int_ventes_par_article') }}
),

achats as (
    select * from {{ ref('int_achats_par_article') }}
),

retours as (
    select * from {{ ref('int_retours_par_article') }}
),

cout_revient as (
    select * from {{ ref('mart_cout_revient_article') }}
),

article as (
    select
        article_key,
        numero_article,
        a_plusieurs_unites,
        unite_principale,
        unite_vente_coherente_avec_production
    from {{ ref('dim_article') }}
),

assemble as (

    select
        a.article_key,
        a.numero_article,
        a.unite_principale,
        a.a_plusieurs_unites,
        a.unite_vente_coherente_avec_production,

        coalesce(v.quantite_totale_vendue, 0) as quantite_vendue,
        coalesce(v.chiffre_affaires, 0) as chiffre_affaires_brut,
        coalesce(r.montant_total_retours, 0) as montant_retours,
        coalesce(v.chiffre_affaires, 0) + coalesce(r.montant_total_retours, 0)
            as chiffre_affaires_net,

        ac.cout_unitaire_moyen_pondere as cout_unitaire_achat_direct,
        ac.quantite_totale_achetee,

        cr.cout_revient_estime,
        cr.nb_matieres_premieres,
        cr.toutes_matieres_ont_cout_achat,
        cr.contient_commande_multi_produits,

        case
            when cr.article_fini is not null then 'nomenclature'
            when ac.cout_unitaire_moyen_pondere > 0 then 'achat_direct'
            else null
        end as methode_cout,

        coalesce(cr.cout_revient_estime, ac.cout_unitaire_moyen_pondere)
            as cout_unitaire_retenu

    from article a
    left join ventes v on a.numero_article = v.numero_article
    left join achats ac on a.numero_article = ac.numero_article
    left join retours r on a.numero_article = r.numero_article
    left join cout_revient cr on a.numero_article = cr.article_fini

),

avec_cout as (

    select
        *,
        case
            when cout_unitaire_retenu is not null
                then round(quantite_vendue * cout_unitaire_retenu, 2)
            else null
        end as cout_estime_vendu

    from assemble

),

avec_marge as (

    select
        *,
        case
            when cout_estime_vendu is not null
                then round(chiffre_affaires_net - cout_estime_vendu, 2)
            else null
        end as marge_estimee,

        case
            when cout_estime_vendu is not null and chiffre_affaires_net != 0
                then round(100.0 * (chiffre_affaires_net - cout_estime_vendu)
                    / nullif(chiffre_affaires_net, 0), 1)
            else null
        end as marge_pct

    from avec_cout

),

avec_niveau as (

    select
        *,
        case
            when cout_estime_vendu is null or cout_unitaire_retenu is null or quantite_vendue = 0
                then 'indetermine'
            when a_plusieurs_unites
                then 'faible'
            when methode_cout = 'nomenclature' and (not toutes_matieres_ont_cout_achat or contient_commande_multi_produits)
                then 'moyenne'
            when methode_cout = 'nomenclature' and unite_vente_coherente_avec_production = false
                then 'faible'
            when methode_cout = 'achat_direct' and (cout_unitaire_achat_direct is null or cout_unitaire_achat_direct = 0)
                then 'faible'
            else 'haute'
        end as niveau_confiance

    from avec_marge

)

select
    *,
    (niveau_confiance = 'haute') as marge_fiable
from avec_niveau