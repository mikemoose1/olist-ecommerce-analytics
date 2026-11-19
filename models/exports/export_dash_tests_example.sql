-- Dashboard panel 6 (text table): the two fix tests, with INVENTED example numbers. The tests have not run.
-- Grain: one row per test (2 rows). PK: test_id. Every row says EXAMPLE three ways so it cannot pass for a result:
-- is_example, the banner text, and an asterisk on every value. When real results exist, a results model replaces this
-- one and the test assert_dash_tests_are_labelled_example is deleted with the seed.
select
    test_id,
    'EXAMPLE test: ' || test_name as test_label,
    'EXAMPLE: ' || readout_metric as readout_label,
    test_group_value,
    no_change_group_value,
    case unit when 'percent' then format('{:.1f}%*', test_group_value) else format('{:.2f}*', test_group_value) end as test_group_display,
    case unit when 'percent' then format('{:.1f}%*', no_change_group_value) else format('{:.2f}*', no_change_group_value) end as no_change_group_display,
    is_example,
    'not run' as status,
    'EXAMPLE DATA · these tests have not run yet' as banner,
    '* invented, only to show the layout' as footnote
from {{ ref('dash_tests_example') }}
order by test_id
