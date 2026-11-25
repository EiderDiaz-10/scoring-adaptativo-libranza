# Figuras de la Fase 2 (EDA)

| Código | Archivo | Mensaje |
|---|---|---|
| E01 | `figuras/fase2/E01_evolucion_cartera.png` | La cartera crece con fuerza desde 2025, se vuelve más recurrente y el buró solo aparece en los últimos trimestres. |
| E02 | `figuras/fase2/E02_histogramas_numericas.png` | Montos, cuotas y mora previa tienen colas largas a la derecha; la edad y la tasa son casi simétricas. |
| E03 | `figuras/fase2/E03_frecuencias_categoricas.png` | El 80 % de los créditos figura con recaudo empresarial y el 53 % son de clientes sin crédito previo. |
| E04 | `figuras/fase2/E04_mapa_faltantes.png` | El buró y la PILA faltan por completo antes de dic-2025: es un faltante estructural, no aleatorio. |
| E05 | `figuras/fase2/E05_correlacion_spearman.png` | Plazo y número de cuotas son casi la misma variable, y monto y cuota están fuertemente ligados: hay que elegir uno de cada par. |
| E06 | `figuras/fase2/E06_tasa_por_categoria.png` | Casi todos los IC se superponen con la tasa global: con 16 eventos ninguna categoría se separa con claridad. |
| E07 | `figuras/fase2/E07_iv_con_ic.png` | Solo unas pocas variables superan el IV esperado por puro ruido, y todos los IC son muy anchos. |
| E08 | `figuras/fase2/E08_perfiles_woe.png` | Los perfiles de las variables con más IV se apoyan en 2 a 6 eventos por intervalo: son señales, no relaciones estimadas. |
| E09 | `figuras/fase2/E09_curvas_cosecha.png` | La cohorte 2022 es atípica (11,5 % alguna vez 90+ al mes 12); 2023–2025 son estables en 90+ (2,4–2,9 %), aunque 2024 tuvo más mora temprana 30+. |
| E10 | `figuras/fase2/E10_km_por_grupo.png` | Solo la cohorte separa las curvas (log-rank p = 0,016, por el arranque 2022); recurrencia y monto apuntan en la dirección esperada pero no son significativos. |
| E11 | `figuras/fase2/E11_tasa_por_semestre.png` | Fuera del arranque de 2022, la tasa 90+/12m oscila entre 1 % y 4 % por semestre; los IC se superponen y no se distingue deriva del evento. |
| E12 | `figuras/fase2/E12_psi_por_trimestre.png` | Recaudo, aval, tasa, tipo de solicitud y cobros cambian de forma abrupta (política); la historia del cliente y del empleador deriva por maduración; la edad es la más estable. |
| E13 | `figuras/fase2/E13_fintech_vs_home_credit.png` | Un clasificador distingue casi perfectamente la fuente de cada registro: Home Credit no es intercambiable con la cartera de libranza. |
