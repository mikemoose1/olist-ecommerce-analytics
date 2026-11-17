{{ config(severity = 'warn') }}
-- Known source gap (warn only): orders whose ship-to zip has no valid point in the geolocation file.
-- 279 orders today (278 zips absent from the file, 1 zip whose points are all outside Brazil).
select order_id, ship_to_zip_code_prefix
from {{ ref('fct_orders') }}
where ship_to_lat is null
