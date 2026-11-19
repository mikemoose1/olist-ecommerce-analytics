-- Rule: the control limits are fitted in a fixed number of passes (set aside the months outside the limits, refit).
-- The last pass must set aside no further month; if it does, the pass count in the model is too small.
select year_month, laney_signal, fit_changed_in_last_pass
from {{ ref('metric_late_rate_control_chart') }}
where fit_changed_in_last_pass
