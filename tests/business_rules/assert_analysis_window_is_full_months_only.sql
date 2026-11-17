-- Rule: trend metrics only use full months. An order is in the analysis window exactly when it was
-- purchased between 2017-01-01 and 2018-08-31; partial edge months are always out.
select order_id, purchase_date, in_analysis_window
from {{ ref('fct_orders') }}
where in_analysis_window
   <> (purchase_date between date '{{ var("analysis_window_start") }}' and date '{{ var("analysis_window_end") }}')
