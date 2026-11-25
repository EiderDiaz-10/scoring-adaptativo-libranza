# Informe de la Fase 5 — Evaluación financiera y de negocio

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Notebook 14 (`14_evaluacion_financiera.ipynb`) y módulo `src/tesis_v2/financiero.py`. Figuras F01–F05 en `catalogo_figuras.md`. Todas las tablas están reunidas en `p12_v2_financiero.xlsx`.

**Base de cálculo.** Uso las predicciones fuera de pliegue promediadas de la validación principal (733 créditos, 23 incumplimientos), con M2 como modelo elegido y M3 como comparación. Los IC salen de un *bootstrap* de clientes con 2.000 réplicas. El *backtest* 2025+ aparece solo como ilustración.

## 1. Supuestos

| Elemento | Supuesto |
|---|---|
| EAD | Monto desembolsado (cota superior) |
| LGD | Escenarios de 25, 45 y 65 % (protocolo), más la LGD observada (59 %, ponderada por exposición) |
| Ingreso | Intereses de 12 meses de un crédito de cuota fija a la tasa pactada; sin comisiones, seguro ni estudio |
| Fondeo | 1,0 % mensual (hipotético), con sensibilidad de 0,5 a 1,5 % |
| Crédito que incumple | Sin ingreso; pierde LGD × EAD |

Con estos supuestos, la cartera tiene un monto de 4.192 millones de COP y un ingreso neto a 12 meses de 302 millones si nadie incumpliera (7,2 % del monto).

## 2. LGD observada (dato nuevo, no previsto en el protocolo)

Las tablas de pagos y de saldos mensuales permiten medir la recuperación de los 23 incumplimientos. La exposición es el saldo de capital al llegar a 90+; la recuperación, los pagos en efectivo posteriores, descontados a la tasa pactada.

- **Es bimodal:** 8 créditos se recuperan por completo y 5 no recuperan nada.
- **Media por crédito: 46 % [28–64 %].** Ponderada por exposición: **59 % [46–75 %]**.
- **El aval la reduce drásticamente:** 15 % con aval (n = 8) frente a 62 % sin aval (n = 15).
- La LGD es mayor en los incumplimientos más antiguos (54 % frente a 39 %). Se explica por la composición: los recientes tienen aval. No hay señal de que la censura la infle.

El escenario central del protocolo (45 %) es razonable para un crédito promedio, pero corto para la cartera en pesos.

## 3. Pérdida esperada frente a realizada

La PD media de M2 coincide con la tasa observada y, aun así, **la pérdida esperada subestima la realizada en cerca de 27 %** en todos los escenarios: 72 frente a 99 millones con LGD 45 %. Los incumplimientos se concentran en créditos más grandes de lo que la PD anticipa. Con la tasa base la subestimación es de 39 %.

La pérdida observada con las recuperaciones reales es de **115 millones**, el 2,7 % del monto desembolsado.

## 4. Bandas A–E (límites relativos a *p* = 3,14 %)

| Banda | M2: créditos (mora %) | M3: créditos (mora %) |
|---|---|---|
| A (< 0,5*p*) | 40 (5,0) | 120 (1,7) |
| B (0,5*p* – *p*) | 402 (1,7) | 310 (1,6) |
| C (*p* – 2*p*) | 254 (4,7) | 252 (4,8) |
| D (2*p* – 4*p*) | 37 (5,4) | 51 (7,8) |
| E (≥ 4*p*) | 0 | 0 |
| Tendencia (Cochran–Armitage) | p = 0,06 | **p = 0,003** |

- **M3 produce bandas monótonas y M2 no.** Es el resultado de la tesis en que M3 más se separa de M2.
- **Ninguno llega a la banda E**, porque la contracción comprime las PD (máximo de 9,6 %).
- **En 2025+ las bandas no se sostienen:** A 4,0 %, B 0,7 %, C 6,5 % y D 0 %, con 5 eventos.

## 5. Curvas de aprobación y punto de corte

- **La mora baja al aprobar menos:** con el 70 % de menor PD queda en 1,75 % [0,6–3,0 %], frente a 3,14 % al aprobar todo.
- **El margen no mejora:**
  - el margen de aprobar todo es 185 millones (LGD 45 %, fondeo de 1 %);
  - el ingreso crece con el monto igual que el riesgo, así que rechazar los de mayor PD es rechazar los créditos que más ingreso dan.
- **Corte óptimo en la muestra:**
  - M2: aprobar a todos con LGD 25 % y 45 %;
  - M3: rechazar el 3 % de mayor PD.
- **Los dos "óptimos" coinciden con un solo crédito:** el incumplimiento de 83 millones, el 38 % de toda la exposición incumplida.
- **Fuera de la bolsa** (umbral elegido en la réplica *bootstrap* y aplicado a los clientes que quedaron fuera), **la ganancia esperada de cualquier corte es negativa**: de −4 a −39 millones por cada 1.000 créditos.
- **Regla de margen esperado crédito a crédito.** La PD de equilibrio mediana es 12 % (LGD 45 %, fondeo de 1 %), muy por encima del máximo de M2. La regla solo rechaza 27 créditos de ingreso muy bajo, todos buenos, y reduce el margen. Con fondeo de 1,5 % parte de la cartera tiene margen negativo **por precio**, no por riesgo.

## 6. Comparación con la regla de políticas vigente (M0b)

La regla marca 112 créditos (15,3 %). Rechazando ese mismo número:

| Estrategia | Malos evitados [IC 95 %] | Buenos rechazados | Cambio de margen frente a aprobar todo (M COP) |
|---|---|---|---|
| Regla M0b | 3 [0–7] | 109 | +12,7 [−40,9; +98,3] |
| M2 | **7** [3–14] | 105 | −19,0 [−73,1; +76,5] |
| M3 | **8** [3–14] | 104 | −15,0 [−74,3; +82,1] |
| Azar (esperado) | 3,5 | 108,5 | −28,3 |

- **Los modelos evitan más incumplimientos que la regla:** +4 [−1; +11] con M2 y +5 [0; +11] con M3. La regla no supera al azar.
- **La ventaja de la regla en margen viene de un solo crédito:** su filtro de monto (> 45 millones) deja fuera el incumplimiento de 83 millones. Sin ese crédito, la regla pierde 25 millones y M2 pierde 56.
- Ningún cambio de margen es significativo.

## 7. Qué podemos y qué no podemos afirmar

**Podemos afirmar:**

- La LGD observada en libranza es de cerca de 46 % por crédito y 59 % ponderada, y el aval la reduce a cerca de 15 %.
- Ordenar con M2 o M3 identifica más incumplimientos que la regla de políticas, rechazando el mismo número de créditos.
- Las bandas de M3 son monótonas dentro de la muestra.

**No podemos afirmar:**

- Que un corte por PD mejore el margen: fuera de la muestra, el efecto esperado es negativo.
- Que las bandas se mantengan en cohortes futuras.
- Que PD × LGD × monto sea una pérdida esperada suficiente: subestima en cerca de 27 %.

## 8. Recomendaciones para el despliegue (insumo de la Fase 6)

1. **Bandas como apoyo, no rechazo automático.** Usar el modelo para asignar bandas amplias (A+B frente a C+D) que fijen **condiciones del crédito**: exigir aval en C y D, limitar el monto y ajustar el precio.
2. **Aval.** Es la palanca con efecto medible: reduce la LGD de 62 % a 15 %.
3. **Pérdida esperada con LGD diferenciada** por aval y un factor de prudencia sobre la exposición de los créditos grandes.
4. **Recalibrar el intercepto** a la tasa reciente antes del primer uso, porque todos los modelos sobrestiman 2025+.
5. **Seguir la LGD por aval** a medida que maduren más incumplimientos. Hoy son 23, con 8 con aval.

## 9. Criterios de aceptación del plan

| Criterio | Estado |
|---|---|
| EL = PD × LGD × EAD con escenarios de LGD; LGD estimada si hay información de recuperación | ✔ escenarios más LGD observada |
| Curvas de aprobación frente a mora y frente a margen; corte óptimo con IC *bootstrap* | ✔ con estimación fuera de la bolsa |
| Bandas A–E con criterio de negocio y monotonía con IC | ✔ Wilson y Cochran–Armitage |
| Comparación frente a la regla actual: malos evitados y buenos rechazados | ✔ con IC pareados |
| Entregables `p12_v2_financiero.xlsx` y F01–F05 | ✔ |

Etiqueta de git: `v2-fase5`.
