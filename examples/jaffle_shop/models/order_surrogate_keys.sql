select
    order_id,
    {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key
from {{ ref('stg_orders') }}
