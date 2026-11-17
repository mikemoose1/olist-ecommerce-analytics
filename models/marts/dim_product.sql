-- Grain: one row per product. PK: product_id.
-- Category in English: source translation, then a seed patch for the 2 untranslated names, else 'unknown'.
select
    p.product_id,
    p.product_category_name,
    coalesce(t.product_category_name_english, patch.product_category_name_english,
             case when p.product_category_name is null then 'unknown' end) as category,
    p.product_name_length, p.product_description_length, p.product_photos_qty,
    p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm
from {{ ref('stg_products') }} p
left join {{ ref('stg_category_translation') }} t using (product_category_name)
left join {{ ref('category_translation_patch') }} patch using (product_category_name)
