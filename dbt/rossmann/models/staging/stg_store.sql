with src as (
    select * from {{ source('raw', 'store') }}
)

select
    store_id::int                  as store_key,
    store_type::text               as store_type,
    assortment::text               as assortment,
    case assortment
        when 'a' then 'basic'
        when 'b' then 'extra'
        when 'c' then 'extended'
        else 'unknown'
    end                            as assortment_name,
    competition_distance::numeric  as competition_distance
from src
