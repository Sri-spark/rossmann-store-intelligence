{#-
  Use the custom schema name verbatim (staging / marts) instead of dbt's
  default <target_schema>_<custom> concatenation, so models land in clean,
  predictable schemas that the ETL, analytics, and Evidence layers reference.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
