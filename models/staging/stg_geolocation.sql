-- Grain: one raw geolocation row (no key: 1,000,163 rows for 19,015 zip prefixes). 1:1 with raw.
-- Deduplication to one point per zip happens in int_geo_zip.
select
    geolocation_zip_code_prefix        as zip_code_prefix,
    cast(geolocation_lat as double)    as lat,
    cast(geolocation_lng as double)    as lng,
    geolocation_city                   as city,
    geolocation_state                  as state
from {{ source('olist_raw', 'olist_geolocation_dataset') }}
