{% macro bucket_order_value(column, small_max=50, medium_max=200) %}
case
    when {{ column }} < {{ small_max }} then 'small'
    when {{ column }} < {{ medium_max }} then 'medium'
    else 'large'
end
{% endmacro %}
