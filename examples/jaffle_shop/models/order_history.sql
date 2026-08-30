{{ config(materialized='incremental') }}

select order_id, customer_id, order_date, status
from {{ ref('stg_orders') }}
{% if is_incremental() %}
where order_date > (select max(order_date) from {{ this }})
{% endif %}
