# Informe de la Fase 2 — Análisis exploratorio (EDA)

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Notebooks 05 (descriptivo y faltantes), 06 (bivariado y WoE/IV) y 07 (temporal y deriva). Las figuras E01–E13 y su mensaje de una línea están en `catalogo_figuras.md`.

**Regla de uso de los datos.** El análisis bivariado (WoE/IV, AUC univariado) usa **solo la muestra de desarrollo (< 2025)**: 494 créditos y 16 eventos. Lo hice así para que la selección de variables no use los créditos 2025+, que ya fueron consultados en la v1. Las vistas descriptivas, de cosecha y de deriva incluyen todas las cohortes porque no se usan para escoger variables.

## 1. La cartera cambió mucho (notebooks 05 y 07)

- La originación crece con fuerza desde 2025. La cartera se vuelve más recurrente, con montos más altos.
- El rechazo de solicitudes de libranza subió de 5,5 % (2023) a 27,8 % (2025) y 21,4 % (2026). La población aprobada es cada vez más seleccionada, un **sesgo de selección** que el modelo hereda.
- **Faltantes.** Buró y PILA solo existen desde 2026Q1–Q2: faltan en el 100 % del desarrollo y existen en el 7,6 % de los elegibles 2025+. La mora previa y la antigüedad faltan por diseño (clientes nuevos, 52,8 %).
- **Deriva (PSI frente a 2023).**
  - Las variables de política o registro (recaudo, aval, tasa mensual, tipo de solicitud, cobros de producto) tienen PSI medianos de 2,7 a 7,7.
  - La historia del cliente y del empleador deriva por maduración de la cartera.
  - El monto deriva (0,44); el plazo (0,27) y la edad (0,20) son los más estables.
- **Cosechas.** La cohorte 2022 es atípica (11,5 % alguna vez 90+ al mes 12). De 2023 a 2025 la mora 90+ al mes 12 es estable, entre 2,4 % y 2,9 %. La cohorte 2024 tuvo más mora temprana 30+ (14,5 %), pero se curó antes de llegar a 90+.
- **Supervivencia.** Solo la cohorte separa las curvas (log-rank p = 0,016). Nuevo frente a recurrente (7,4 % frente a 4,2 %) y los terciles de monto (2,8 % → 7,2 %) van en la dirección esperada, pero no son significativos.

## 2. Señal de las variables (notebook 06)

- El IV que se obtiene **por puro ruido** con 16 eventos tiene un percentil 95 de **0,45**. Solo `monto` (IV 0,63; IC por cliente 0,45–1,13; AUC 0,67) y `cuota_mensual`, redundante con monto y plazo, lo superan. La señal de `monto` no se repite con 60+/12m ni con 30+/6m.
- `emp_creditos_previos` (experiencia del empleador con FINTECH) tiene una señal protectora consistente en las tres definiciones (AUC 0,31, es decir, 0,69 invertido). Crece con el calendario, así que se debe evaluar dentro de la cohorte.
- `peor_mora_previa` y `n_activos_t0` muestran el signo contrario al esperado, con IC que incluyen 0,5. Las conservo por dominio, no por los datos.
- **`recaudo` es un indicador de época.** El recaudo directo existe solo hasta 2023Q3, y dentro de 2023 su relación con el evento se invierte. Queda fuera del núcleo hasta aclarar su significado con la operación.
- `tipo_solicitud` y `es_refinanciacion` solo distinguen la refinanciación desde 2024Q2. `cobra_seguro` y `cobra_estudio` son constantes antes de 2025.
- La propuesta de variables para la Fase 3 está en `propuesta_variables_fase3.csv`.
  - **Núcleo:** monto (vigilando su deriva), plazo, edad, créditos previos, antigüedad, recurrencia, cierre previo, peor mora previa por dominio, y experiencia del empleador.
  - **Fuera:** política, buró y PILA en el modelo con datos propios, género y huella digital.

## 3. Home Credit frente a FINTECH (notebook 07)

Un clasificador adversarial distingue la fuente de cada registro con un **AUC de 0,96** usando cinco variables comparables. Solo la edad se parece (SMD −0,18). La antigüedad como cliente en Home Credit triplica la de FINTECH (mediana de 50 frente a 14 meses). Además, el evento es distinto y la tasa base es del 9,0 %, frente al 2,9 % de FINTECH. **Home Credit es otra población.** Esto respalda usarla como *prior* con escala ajustable (M3) y no como datos apilados con peso fijo, como en la v1.

## 4. Implicaciones para la Fase 3

1. El modelo debe ser **parsimonioso** (0,7 a 2 parámetros efectivos con los datos propios), con penalización o información previa.
2. El tiempo es un confusor de primer orden (cohorte, política, maduración). La validación agrupada repetida es la principal; el *backtest* temporal la complementa.
3. Las variables de política no entran al núcleo. El monto entra vigilado y se reporta su contribución dentro de la cohorte.
4. Todas las conclusiones sobre variables individuales son **señales**, no efectos estimados: los IC son muy anchos.
