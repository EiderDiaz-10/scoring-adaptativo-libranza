# Informe de la Fase 1 — Auditoría de datos, objetivo y dataset analítico

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Fuente: exportación FINTECH del 2026-10-08 (solo lectura). Todas las cifras son agregadas; el detalle está en los notebooks 01 a 04 y en las tablas CSV de esta carpeta.

## 1. Qué hice

1. **Auditoría de tablas (notebook 01).** Revisé el inventario, las llaves, los duplicados, la integridad referencial, la consistencia de fechas y valores, y las columnas con información posterior a t0. Resumí todo en 53 reglas de calidad (`reglas_calidad.csv`).
2. **Objetivo y población (notebook 02).** Reconstruí la mora diaria con la regla FIFO (plan vigente contra pagos válidos) y apliqué las reglas D3–D6. Construí los objetivos 90+/12m (primario), 60+/12m y 30+/6m, la variante B y el tiempo hasta 90+ para supervivencia.
3. **Dataset analítico (notebook 03).** Todas las variables se calculan con información disponible en t0. La historia del cliente llega hasta t0 − 1 día y el buró solo con consultas hechas hasta el desembolso. El género está excluido. El resultado son 1.161 créditos y 63 columnas, guardado en `_privado/`.
4. **Tamaño muestral (notebook 04).** Apliqué los criterios de Riley et al. (2020) y calculé la potencia del AUC. Los resultados quedaron en el Anexo A del protocolo, antes de cualquier modelo.

## 2. Resultados principales

| Indicador | Valor |
|---|---|
| Créditos no anulados | 1.161 (1.087 de libranza) |
| Población primaria (libranza elegible, 90+/12m) | 731 créditos, 356 clientes, **21 eventos (2,87 %; IC 95 % 1,9–4,4)** |
| Desarrollo (< 2025) / prueba temporal (2025+) | 494 créditos con 16 eventos / 237 con 5 |
| 60+/12m · 30+/6m | 27 eventos (3,69 %) · 62 eventos en 788 créditos (7,87 %) |
| Coincidencia con el objetivo v1 | 100 % en cierres, DPD máximo, elegibilidad y etiquetas |
| Sensibilidad a la tolerancia (0 %–10 %) | Sin cambios; la ventana D4 mueve el conteo entre 20 y 22 eventos |
| Indeterminados maduros | 42 créditos; cotas de la tasa: 2,72 %–8,15 % |
| Kaplan-Meier a 12 meses (libranza 2022+) | 5,7 %, frente al 2,9 % de la tasa binaria |
| Parámetros soportados (Riley, S ≥ 0,9) | 0,7 a 2 para 90+/12m; 1,9 a 5,6 para 30+/6m |
| Diferencia de AUC detectable | ≈ 0,18 |

## 3. Hallazgos de calidad y cómo los resolví

- **Identidad.** Una persona aparecía con dos id de cliente; lo detecté con un chequeo de documentos que solo produce conteos. Creé un grupo de cliente unificado (`_privado/grupo_cliente_v2.parquet`) para que la validación agrupada no reparta a la misma persona entre entrenamiento y prueba.
- **Fuga en las tablas.** `estado`, `categoria_credito` y `en_refinanciacion` describen el crédito después de t0 y quedan fuera como predictores. Había además **38 consultas de buró posteriores al desembolso**, una fuga que en el dataset v2 ya está filtrada.
- **Fechas.** 194 créditos (16,7 %) no tienen solicitud enlazada; para ellos t0 es la fecha de inicio. En 26 la solicitud es posterior al inicio; para esos t0 es la fecha más temprana de las dos. Tres edades están fuera de 18–80 años y se marcaron como faltantes.
- **Pagos.** No hay pagos activos duplicados exactos. Hay 7 casi duplicados que se conservan porque pueden ser cuotas legítimas del mismo día.
- **Reporte del empleador (`pagosempresas`).** Su concordancia con la mora reconstruida es moderada (kappa ≈ 0,47). Sirve como validación cruzada, no como fuente de la etiqueta.
- **Créditos 131 y 250.** Están en el grupo de indeterminados, con saldo y sin crédito posterior, pero su mora supera 90 días dentro de los 12 meses (113 y 218 días). Lógicamente son eventos. Quedan señalados en `creditos_131_250_para_verificar.csv`. Si la operación confirma que no hubo pago por fuera, la población primaria pasa a **733 créditos con 23 eventos**. **No se reclasificaron sin la confirmación de Eider.**

## 4. Lo que significa para el modelado

- La incertidumbre más grande de la etiqueta no es la tolerancia ni la ventana de refinanciación, sino los **42 indeterminados**: la tasa puede ir de 2,7 % a 8,2 %. Por eso el protocolo incluye un análisis de sensibilidad con las dos cotas.
- El 71 % de la cartera de libranza no ha cumplido 12 meses (riesgos competitivos y censura). La supervivencia aprovecha esa información, aunque solo agrega un evento.
- Con 21 eventos, cualquier modelo de más de dos parámetros efectivos necesita contracción fuerte o información externa. Comparar modelos por su AUC puntual no tiene sustento.
