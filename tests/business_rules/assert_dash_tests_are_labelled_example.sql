-- Rule (dashboard panel 6): while the two fix tests have not run, every number in the "are the fixes working" panel is
-- labelled as invented example data. In the seed AND in the export: is_example is true on every row (null counts as a
-- failure), every row says "not run", the test and readout labels start with EXAMPLE, every value carries an asterisk, and the
-- banner and footnote are there. The export keeps all of the seed's rows. When real results exist, a results model replaces
-- the seed, and this test goes with it.
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
union all select 'export has ' || (select count(*) from e)::varchar || ' rows but the seed has ' || (select count(*) from seed)::varchar where (select count(*) from e) <> (select count(*) from seed)
union all select 'the seed is empty' where (select count(*) from seed) = 0
