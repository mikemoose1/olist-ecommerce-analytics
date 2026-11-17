-- Rule: the build only runs on the exact published raw files.
-- Fails with one row per file whose sha256 differs from the pinned manifest (or is missing).
with manifest as (
    select file_name, sha256 from {{ ref('raw_file_manifest') }}
),
actual as (
    select regexp_extract(filename, '[^/]+$') as file_name, sha256(content) as sha256
    from read_blob('{{ env_var("OLIST_RAW_DIR", "data/raw") }}/*.csv')
)
select m.file_name, m.sha256 as expected, a.sha256 as actual
from manifest m
left join actual a using (file_name)
where a.sha256 is null or a.sha256 <> m.sha256
