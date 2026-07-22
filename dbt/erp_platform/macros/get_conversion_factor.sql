{% macro get_conversion_factor(code_column) %}
    case
        -- Cartons : extrait le premier nombre après "CRT-"
        -- Ex: CRT-12*1 -> 12, CRT-12 VRC -> 12, CRT-12*500 -> 12
        when {{ code_column }} like 'CRT-%' then
            cast(
                substring({{ code_column }} from '^CRT-([0-9]+)') as numeric
            )
        -- Poids (votre métier : 1 QUINTAL = 1000 KG)
        when {{ code_column }} = 'QUINTAL' then 1000.0
        when {{ code_column }} = 'KG'      then 1.0
        -- Unitaires et conditionnement (facteur 1)
        when {{ code_column }} in ('UNITE', 'LITRE', 'SAC', 'FARDEAU', 'CARTON') then 1.0
        -- Sécurité : si unité inconnue, on suppose 1 (mais on garde une trace)
        else 1.0
    end
{% endmacro %}