# Informe de la Fase 4 — Modelos y validación robusta

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Notebooks 09 (validación cruzada), 10 (comparación y selección), 11 (interpretabilidad), 12 (sensibilidades e inferencia de rechazados) y 13 (*backtest* temporal). Figuras M01–M12 en `catalogo_figuras.md`. Las tablas de esta carpeta están reunidas en `p6_v2_modelos.xlsx`. La ficha del modelo elegido está en `ficha_modelo_v2.md`.

## 1. Diseño

- **Batería cerrada** del protocolo, M0a a M7, con 11 modelos en total.
- **Mismas particiones para todos:** 5 pliegues por cliente × 20 repeticiones, es decir, 100 ajustes por modelo, con hiperparámetros elegidos en un 3-fold interno agrupado.
- **IC 95 %** por *bootstrap* de clientes (2.000 réplicas), con las mismas réplicas para todos los modelos, así que las comparaciones son pareadas.
- **Regla de selección preespecificada** (enmienda v1.1, sección 5).

## 2. Resultados principales (`tabla_unica_resultados.csv`)

| Modelo | Log loss | AUC [IC 95 %] | Pendiente de calibración | Brier escalado |
|---|---|---|---|---|
| M0a Tasa base | 0,1396 | 0,474 | — | 0,000 |
| M0b Regla de políticas | 0,1416 | 0,391 [0,32–0,45] | — | −0,004 |
| M1 *Scorecard* WoE | 0,1511 | 0,547 [0,43–0,66] | 0,08 | −0,017 |
| **M2 Logística penalizada** | **0,1387** | **0,629 [0,50–0,75]** | **0,62** | 0,005 |
| M2F Firth | 0,1483 | 0,600 [0,48–0,72] | 0,22 | −0,048 |
| M3 *Prior* Home Credit | 0,1366 | 0,653 [0,53–0,78] | 0,77 | 0,010 |
| M4 Apilado v1 | 0,1377 | 0,644 [0,52–0,78] | 0,57 | 0,019 |
| M5 *Boosting* monótono | 0,1371 | 0,633 [0,52–0,75] | 0,72 | 0,005 |
| M6 Supervivencia | 0,1426 | 0,602 [0,48–0,73] | 1,17 | −0,012 |
| M7 60+ → 90+ | 0,1389 | 0,642 [0,52–0,76] | 0,53 | 0,005 |
| M7 30+ → 90+ | 0,1392 | 0,605 [0,49–0,72] | 0,53 | 0,001 |

**Regla de selección** (`regla_de_seleccion.csv`):

1. Son elegibles los modelos con pendiente de calibración entre 0,6 y 1,4: M2, M3, M5 y M6.
2. El de menor log loss entre ellos es M3.
3. M3 frente a M2: Δ −0,0021 [−0,0049; +0,0006]. El IC incluye 0, así que se elige **el más simple, M2**.
4. M2 frente a la tasa base: Δ −0,0009 [−0,0084; +0,0074]. **La mejora no es demostrable.**

**Otras comparaciones** (`comparaciones_pareadas.csv`, con corrección de Holm):

- M2, M3, M4, M5 y M7 superan a M1 en log loss con p de Holm ≤ 0,02.
- En AUC frente a la tasa base, ningún modelo la supera de forma significativa después de Holm; el menor p es 0,09, para M3.
- La regla de políticas M0b ordena **al revés** (AUC 0,39, IC por debajo de 0,5): los créditos que violan alguna política incumplen igual o menos que los demás.

## 3. Calibración, optimismo y utilidad clínica

- **Calibración.** Con 23 eventos, solo es verificable en el rango bajo de PD, por debajo de 5 % (M02). M2 queda sobreajustado aun con la penalización: pendiente 0,62.
- **Optimismo de Harrell** (500 réplicas): el AUC aparente de 0,726 baja a 0,675 corregido, frente a 0,629 en la validación cruzada. La validación cruzada repetida es la estimación más conservadora y la que reporto.
- **Curva de decisión** (M03): los modelos superan a "aprobar a todos" y a "rechazar a todos" solo entre umbrales de 3 % y 6 %, con un beneficio neto máximo de cerca de 8 por 1.000 créditos.

## 4. Interpretabilidad (notebook 11)

- **M2:** ningún coeficiente tiene un IC que excluya el 0 (M04). Las señales más consistentes, con probabilidad de tener el signo esperado ≥ 93 %, son:
  - experiencia del empleador, protectora (OR 0,72 por desviación estándar);
  - monto, que aumenta el riesgo (OR 1,27);
  - edad, protectora (OR 0,82);
  - antigüedad como cliente, protectora (OR 0,85).
- **M5** usa solo cinco variables, sin interacciones (M05).
- **En Cox**, solo dos variables son significativas: la experiencia del empleador (HR 0,56) y, contra la hipótesis, el plazo largo (HR 0,44) (M06).
- **`n_activos_t0` y `tiene_historia` tienen signo contrario al esperado en todos los modelos.**

## 5. Sensibilidades (notebook 12, `sensibilidades.csv`)

- **La conclusión central resiste.** El IC del Δ log loss de M2 frente a la tasa base incluye 0 en los 12 escenarios. El AUC de M2 va de 0,61 a 0,63 en todas las variantes de etiqueta, ventanas D4 y casos completos.
- **Etiqueta original (731/21):** AUC 0,617. La reclasificación de 131 y 250 no sostiene los resultados.
- **Más eventos, más señal.** Con la variante B (126 eventos), Δ −14,6 × 10⁻³ [−29,8; +0,3]: el problema es sobre todo de tamaño muestral.
- **Sin la cohorte 2022, la señal desaparece** (AUC 0,49 y coeficientes contraídos a 0). Es la sensibilidad más importante, porque la señal depende de la época.
- **`recaudo_directo`** recibe un coeficiente de 0 y no mejora el modelo.
- **τ de M3:** el óptimo es τ = 0,25, que es también el valor que elige el pliegue interno. Un τ menor empeora el centro Home Credit, porque impone dos signos que FINTECH contradice (M07). Apilar más Home Credit (M4) mejora de forma monótona, sin alcanzar a M3.
- **Estabilidad L1** (500 réplicas): el empleador entra en el 93 % de las réplicas, el monto en el 85 % y la edad en el 84 %. La historia previa entra de forma errática, entre 23 y 52 % (M08).
- **Inferencia de rechazados** (202 solicitudes de libranza rechazadas, aumentación difusa con k = 1, 2, 3):
  - el AUC en aprobados no cambia (0,626–0,628);
  - la PD de la población que solicita sube de 3,2 % a 4,6 % bajo el supuesto k;
  - los rechazados se parecen a los aprobados en las variables del modelo (todas las SMD < 0,3) (M09).

## 6. *Backtest* temporal (notebook 13; 2025+ ya consultado en la v1)

- **Diseño:** entrenamiento con < 2025 (496 créditos, 18 eventos) y prueba en 2025+ (237 créditos, 5 eventos). El 57 % de los créditos de prueba son de clientes que ya estaban en el entrenamiento.
- **Ningún modelo discrimina en 2025+:** el AUC de M2 es 0,41 [0,05–0,86] y el de M3 es 0,51. Ninguno mejora a la tasa base en log loss.
- **Todos sobrestiman la PD** (la tasa observada bajó de 3,6 % a 2,1 %). Los que más se acercan son los más contraídos o los que usan información externa (M10, M11).
- **El origen móvil anual** (2023, 2024, 2025+) repite el patrón. **M3 es el que menos se degrada.**
- **Diagnóstico** (M12): ningún predictor mantiene su relación con el incumplimiento entre cohortes. El monto, la señal más regular antes de 2025 (AUC univariado de 0,62 a 0,77), se invierte en 2025+ (0,37). M2 tiene AUC 0,74 en su propio entrenamiento: aprende un patrón que no se repite.

## 7. Qué podemos y qué no podemos afirmar (criterio de aceptación del plan)

La potencia calculada en la Fase 1 ya lo anticipaba (notebook 04, con 21 eventos):

- para tener 80 % de potencia frente al azar hace falta un AUC verdadero cercano a 0,68 (con 0,65 la potencia es 62 %);
- la diferencia de AUC detectable entre dos modelos es de cerca de 0,18;
- la muestra solo sostiene de 0,7 a 2 parámetros efectivos (Riley et al., 2020).

**Podemos afirmar:**

1. Los modelos penalizados o con información previa (M2, M3, M5, M7) **ordenan mejor que el azar dentro de la muestra** (AUC 0,63–0,65; el límite inferior del IC es ≥ 0,50 en todos) y **mejor que el *scorecard* WoE** en log loss.
2. **La regla de políticas vigente no ordena el riesgo**; si acaso lo invierte.
3. Usar Home Credit como ***prior* con escala ajustable** (M3) es mejor que apilarlo con peso fijo (M4, configuración v1) y que no usarlo (M2). La ventaja es pequeña y consistente en todos los escenarios, pero no es significativa.
4. La experiencia del empleador, el monto, la edad y la antigüedad son las señales más estables **dentro de la muestra**.
5. La conclusión de que la mejora no es demostrable **no depende** de la reclasificación de 131 y 250, de la regla D4, de los indeterminados, de la imputación ni de la exclusión de `recaudo`.

**No podemos afirmar:**

1. Que algún modelo **mejore a la tasa base en calidad probabilística** (log loss o Brier). Ningún IC excluye el 0.
2. Que la discriminación **se sostenga en el tiempo**: el *backtest* y el origen móvil la contradicen.
3. Que algún coeficiente individual sea **distinto de 0**.
4. Que la calibración sea correcta **por encima de 5 % de PD**.
5. Nada sobre la PD de los **solicitantes rechazados** más allá del supuesto k.

## 8. Consecuencias para las fases 5 y 6

- **M2 es el modelo elegido** según la regla preespecificada. M3 es la alternativa natural para el despliegue adaptativo: un *prior* centrado en el modelo anterior es justamente un mecanismo de actualización conservador.
- El modelo debe usarse como **apoyo de ordenamiento por bandas**, con recalibración del intercepto a la tasa reciente y monitoreo de la estabilidad de los coeficientes por cohorte.
- **El aprendizaje incremental es indispensable** porque la relación predictor-riesgo cambia entre cohortes. Sus reglas de actualización deben ser conservadoras.

Etiqueta de git: `v2-fase4`.
