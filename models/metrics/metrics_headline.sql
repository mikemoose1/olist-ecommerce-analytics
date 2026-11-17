-- One row per published metric. value_pct holds a percentage for rates and stars for review metrics.
select *, true  as is_headline from {{ ref('metric_repeat_rate_90d') }}
union all
select *, false as is_headline from {{ ref('metric_repeat_rate_ever') }}
union all
select *, false as is_headline from {{ ref('metric_late_rate') }}
union all
select *, false as is_headline from {{ ref('metric_review_score') }}
