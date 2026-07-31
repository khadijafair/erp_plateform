with ventes as (

    select numero_article, chiffre_affaires
    from {{ ref('int_ventes_par_article') }}
    where chiffre_affaires > 0

),

total as (

    select sum(chiffre_affaires) as ca_total from ventes

),

classe as (

    select
        v.numero_article,
        v.chiffre_affaires,

        rank() over (order by v.chiffre_affaires desc) as rang_ca,

        round(
            100.0 * sum(v.chiffre_affaires) over (
                order by v.chiffre_affaires desc
                rows between unbounded preceding and current row
            ) / nullif(t.ca_total, 0)
        , 2) as pct_cumule_ca

    from ventes v
    cross join total t

)

select
    {{ dbt_utils.generate_surrogate_key(['numero_article']) }} as article_key,
    numero_article,
    chiffre_affaires,
    rang_ca,
    pct_cumule_ca,
    case
        when pct_cumule_ca <= 80 then 'A'
        when pct_cumule_ca <= 95 then 'B'
        else 'C'
    end as classe_abc

from classe
order by rang_ca