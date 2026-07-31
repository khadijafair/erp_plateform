with calendrier as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="(select min(date_ecriture) from " ~ ref('stg_erp_ventes_achats') ~ ")",
        end_date="(select max(date_ecriture) + interval '1 day' from " ~ ref('stg_erp_ventes_achats') ~ ")"
    ) }}

)

select
    cast(date_day as date)                     as date_id,
    date_day                                   as date_ecriture,
    extract(year from date_day)::int           as annee,
    extract(quarter from date_day)::int        as trimestre,
    extract(month from date_day)::int          as mois,
    to_char(date_day, 'Month')                 as nom_mois,
    extract(week from date_day)::int           as semaine,
    extract(isodow from date_day)::int         as jour_semaine_iso,
    extract(isodow from date_day) in (6, 7)    as est_weekend

from calendrier