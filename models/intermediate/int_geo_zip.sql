-- Grain: one row per zip code prefix. PK: zip_code_prefix.
-- The raw file has 1,000,163 rows for 19,015 prefixes (261,831 exact duplicates, 42 points outside Brazil).
-- Rule: one point per prefix = median lat/lng of the rows inside Brazil's bounding box;
-- city/state = the most common value.
select
    zip_code_prefix,
    median(lat)   as lat,
    median(lng)   as lng,
    mode(city)    as city,
    mode(state)   as state,
    count(*)      as n_raw_points
from {{ ref('stg_geolocation') }}
where lat between -33.8 and 5.3
  and lng between -74.0 and -34.7
group by zip_code_prefix
