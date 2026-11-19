-- Rule (dashboard panel 6): while the two fix tests have not run, every number in the "are the fixes working" panel is
-- labelled as invented example data. In the seed AND in the export: is_example is true on every row (null counts as a
-- failure), every row says "not run", the test and readout labels start with EXAMPLE, every value carries an asterisk, and the
-- banner and footnote are there. The export keeps all of the seed's rows. When real results exist, a results model replaces
-- the seed, and this test goes with it.
-- Every other column is also compared with the seed (found unchecked by verification/column_sweep.py): the values equal the seed's,
-- the labels are 'EXAMPLE test: ' and 'EXAMPLE: ' plus the seed's names, the displayed values are the seed's values with one
-- decimal and a percent sign (percent) or two decimals (stars) and an asterisk, and the banner and footnote are the exact words.
-- One row per problem; passes when it returns nothing.
with seed as (select * from {{ ref('dash_tests_example') }}),
e as (select * from {{ ref('export_dash_tests_example') }})
select 'seed row ' || test_id::varchar || ' is not flagged is_example' as what from seed where is_example is not true
union all select 'export row ' || test_id::varchar || ' is not flagged is_example' from e where is_example is not true
union all select 'export row ' || test_id::varchar || ' does not say not run' from e where status is distinct from 'not run'
union all select 'export row ' || test_id::varchar || ' test label does not start with EXAMPLE' from e where test_label is null or test_label not like 'EXAMPLE%'
union all select 'export row ' || test_id::varchar || ' readout label does not start with EXAMPLE' from e where readout_label is null or readout_label not like 'EXAMPLE%'
union all select 'export row ' || test_id::varchar || ' test-group value has no asterisk' from e where test_group_display is null or test_group_display not like '%*'
union all select 'export row ' || test_id::varchar || ' no-change value has no asterisk' from e where no_change_group_display is null or no_change_group_display not like '%*'
union all select 'export row ' || test_id::varchar || ' has no EXAMPLE banner' from e where banner is null or banner not like 'EXAMPLE DATA%not run yet'
union all select 'export row ' || test_id::varchar || ' has no invented-numbers footnote' from e where footnote is null or footnote not like '*%invented%'
union all select 'export row ' || e.test_id::varchar || ' differs from the seed: ' || c.what
from e join seed using (test_id)
cross join lateral (
    select unnest(array[
        case when e.test_group_value is distinct from seed.test_group_value then 'test-group value' end,
        case when e.no_change_group_value is distinct from seed.no_change_group_value then 'no-change value' end,
        case when e.test_label is distinct from 'EXAMPLE test: ' || seed.test_name then 'test label' end,
        case when e.readout_label is distinct from 'EXAMPLE: ' || seed.readout_metric then 'readout label' end,
        case when e.test_group_display is distinct from (case seed.unit when 'percent' then printf('%.1f%%*', seed.test_group_value) else printf('%.2f*', seed.test_group_value) end) then 'test-group display' end,
        case when e.no_change_group_display is distinct from (case seed.unit when 'percent' then printf('%.1f%%*', seed.no_change_group_value) else printf('%.2f*', seed.no_change_group_value) end) then 'no-change display' end,
        case when e.banner is distinct from 'EXAMPLE DATA · these tests have not run yet' then 'banner' end,
        case when e.footnote is distinct from '* invented, only to show the layout' then 'footnote' end
    ]) as what
) c
where c.what is not null
union all select 'export has ' || (select count(*) from e)::varchar || ' rows but the seed has ' || (select count(*) from seed)::varchar where (select count(*) from e) <> (select count(*) from seed)
union all select 'the seed is empty' where (select count(*) from seed) = 0
