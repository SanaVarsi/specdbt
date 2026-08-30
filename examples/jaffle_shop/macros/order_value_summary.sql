{#- Composes bucket_order_value: a select-list fragment pairing each
order's raw amount with its tier, so callers don't repeat the pairing. -#}
{% macro order_value_summary(order_id_column, amount_column) %}
{{ order_id_column }},
{{ amount_column }},
{{ bucket_order_value(amount_column) }} as value_bucket
{% endmacro %}
