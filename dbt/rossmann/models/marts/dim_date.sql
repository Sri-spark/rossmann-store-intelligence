-- Date dimension built from the distinct dates present in the sales fact,
-- guaranteeing referential integrity with fct_sales.date_key.
with dates as (
    select distinct sale_date
    from {{ ref('stg_sales') }}
)

select
    (extract(year from sale_date) * 10000
        + extract(month from sale_date) * 100
        + extract(day from sale_date))::int     as date_key,
    sale_date                                     as date_day,
    extract(isodow from sale_date)::int           as day_of_week,   -- 1=Mon .. 7=Sun
    trim(to_char(sale_date, 'Day'))               as day_name,
    extract(month from sale_date)::int            as month,
    trim(to_char(sale_date, 'Mon'))               as month_name,
    extract(year from sale_date)::int             as year,
    extract(quarter from sale_date)::int          as quarter,
    extract(week from sale_date)::int             as week_of_year,
    (extract(isodow from sale_date) in (6, 7))    as is_weekend
from dates
