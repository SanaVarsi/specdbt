{#- Generalizes the hardcoded payment_methods loop in models/orders.sql
into a reusable macro: one summed, aliased column per category value. -#}
{% macro pivot_sum(category_column, categories, amount_column) %}
{%- for category in categories %}
sum(case when {{ category_column }} = '{{ category }}' then {{ amount_column }} else 0 end) as {{ category }}_amount{% if not loop.last %},{% endif %}
{% endfor -%}
{% endmacro %}
