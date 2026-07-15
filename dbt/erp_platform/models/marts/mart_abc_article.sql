{#
  Classement ABC (Pareto) : les articles sont classés par CA net
  décroissant, puis catégorisés selon leur contribution cumulée au CA total.
    Classe A : jusqu'à 80% du CA cumulé (les articles prioritaires)
    Classe B : de 80% à 95%
    Classe C : les 5% restants (longue traîne)
#}

with marge as (

    select article_key, numero_article, chiffre_affaires_net
    from {{ ref('mart_marge_article') }}
    where chiffre_affaires_net > 0   -- on classe uniquement les articles réellement vendus

),

total as (

    select sum(chiffre_affaires_net) as ca_total from marge

),

classe as (

    select
        m.article_key,
        m.numero_article,
        m.chiffre_affaires_net,

        rank() over (order by m.chiffre_affaires_net desc)              as rang_ca,

        round(
            100.0 * sum(m.chiffre_affaires_net) over (
                order by m.chiffre_affaires_net desc
                rows between unbounded preceding and current row
            ) / nullif(t.ca_total, 0)
        , 2)                                                            as pct_cumule_ca

    from marge m
    cross join total t

)

select
    *,
    case
        when pct_cumule_ca <= 80 then 'A'
        when pct_cumule_ca <= 95 then 'B'
        else 'C'
    end                                                                 as classe_abc

from classe
order by rang_ca
