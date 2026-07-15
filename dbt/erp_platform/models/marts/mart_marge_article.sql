{#
  Marge brute ESTIMÉE par article = CA net (ventes - retours) - coût des
  quantités vendues valorisées au CMUP achat.

  Limite assumée et documentée (pas cachée) : le CMUP est calculé sur
  l'unité brute de la colonne quantité, sans conversion inter-unités. Pour
  un article vendu/acheté dans une seule unité (a_plusieurs_unites = false
  dans dim_article), c'est fiable. Pour un article qui mélange plusieurs
  unités, le CMUP mélange des grandeurs non comparables : la marge est
  alors marquée non fiable via marge_fiable = false plutôt que d'afficher
  un chiffre trompeur comme s'il était exact.
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

article as (
    select article_key, numero_article, a_plusieurs_unites, unite_principale
    from {{ ref('dim_article') }}
),

assemble as (

    select
        a.article_key,
        a.numero_article,
        a.unite_principale,
        a.a_plusieurs_unites,

        coalesce(v.quantite_totale_vendue, 0)                          as quantite_vendue,
        coalesce(v.chiffre_affaires, 0)                                as chiffre_affaires_brut,
        coalesce(r.montant_total_retours, 0)                           as montant_retours,
        coalesce(v.chiffre_affaires, 0) + coalesce(r.montant_total_retours, 0)
                                                                        as chiffre_affaires_net,

        ac.cout_unitaire_moyen_pondere,
        ac.quantite_totale_achetee,

        case
            when ac.cout_unitaire_moyen_pondere is not null
                then round(coalesce(v.quantite_totale_vendue, 0) * ac.cout_unitaire_moyen_pondere, 2)
            else null
        end                                                             as cout_estime_vendu

    from article a
    left join ventes v  on a.article_key = v.article_key
    left join achats ac on a.article_key = ac.article_key
    left join retours r on a.article_key = r.article_key

)

select
    *,

    case
        when cout_estime_vendu is not null
            then round(chiffre_affaires_net - cout_estime_vendu, 2)
        else null
    end                                                                 as marge_estimee,

    case
        when cout_estime_vendu is not null and chiffre_affaires_net != 0
            then round(100.0 * (chiffre_affaires_net - cout_estime_vendu) / nullif(chiffre_affaires_net, 0), 1)
        else null
    end                                                                 as marge_pct,

    -- Fiable seulement si l'article a RÉELLEMENT été vendu ET acheté à un
    -- montant non nul (un CMUP à 0 vient d'un achat enregistré à montant 0 -
    -- échantillon gratuit, transfert interne, ou erreur de saisie -, pas
    -- d'une vraie acquisition gratuite : on l'exclut plutôt que d'afficher
    -- une marge de 100% trompeuse), et sur une seule unité. Sur ce jeu de
    -- données, ne concerne qu'une minorité d'articles : l'essentiel du
    -- catalogue vendu (produits finis) n'a pas de contrepartie achat directe
    -- (matières premières), voir dim_article pour le constat complet.
    (cout_estime_vendu is not null and cout_unitaire_moyen_pondere > 0
     and quantite_vendue > 0 and not a_plusieurs_unites)                as marge_fiable

from assemble
