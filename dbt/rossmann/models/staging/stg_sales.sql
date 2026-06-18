with src as (
    select * from {{ source('raw', 'sales') }}
)

select
    store_id::int                       as store_key,
    sale_date::date                     as sale_date,
    day_of_week::int                    as day_of_week,
    coalesce(sales, 0)::numeric         as sales,
    coalesce(customers, 0)::int         as customers,
    coalesce(open_flag, 0)::int         as open_flag,
    coalesce(promo, 0)::int             as promo,
    coalesce(state_holiday, '0')::text  as state_holiday,
    coalesce(school_holiday, 0)::int    as school_holiday
from src
