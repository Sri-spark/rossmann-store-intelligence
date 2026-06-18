-- Store dimension (one row per store).
select
    store_key,
    store_type,
    assortment,
    assortment_name,
    competition_distance
from {{ ref('stg_store') }}
