-- Grain: one row per zip code prefix in the source. PK: zip_code_prefix.
-- The raw file has 1,000,163 rows for 19,015 prefixes (261,831 exact duplicates, 42 points outside Brazil).
-- Rule: one point per prefix = median lat/lng of the rows inside Brazil's bounding box; city/state = the most
-- common value. A prefix whose points are ALL outside Brazil (5 prefixes) is kept with null coordinates and
-- has_valid_point = false, so it is visible instead of silently dropped.
with flagged as (
    select *, (lat between -33.8 and 5.3 and lng between -74.0 and -34.7) as in_brazil
    from {{ ref('stg_geolocation') }}
)
select
    zip_code_prefix,
    median(lat) filter (where in_brazil)  as lat,
    median(lng) filter (where in_brazil)  as lng,
    mode(city)                            as city,
    mode(state)                           as state,
    count(*)                              as n_raw_points,
    bool_or(in_brazil)                    as has_valid_point
from flagged
group by zip_code_prefix
