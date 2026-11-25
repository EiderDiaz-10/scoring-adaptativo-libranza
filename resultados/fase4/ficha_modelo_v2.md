# Ficha del modelo — M2, logística penalizada (tesis v2)

Formato de *model card* de Mitchell et al. (2019). Versión: protocolo v1.1, etiqueta de git `v2-fase4`, 15-nov-2026. Autor: Eider Johan Díaz Berrío. Asesor: Juan Alejandro Peña Palacio. Maestría en Ciencias de los Datos y Analítica, EAFIT.

## 1. Qué es

- **Tipo:** regresión logística con penalización L2 (C = 0,1), elegida con un 3-fold interno agrupado por cliente sobre una grilla de L2, L1 y *elastic net*. Hay 11 predictores estandarizados y la edad se imputa con la mediana.
- **Qué predice:** la probabilidad de que un crédito de libranza llegue a **90 días o más de mora en los primeros 12 meses** desde el desembolso (definición de incumplimiento en consumo de la SFC, CBCF, Capítulo II). Los días de mora se reconstruyen día a día, con imputación FIFO de los pagos.
- **Cómo se eligió:** con la regla preespecificada del protocolo. M3 (*prior* de Home Credit) tuvo menor log loss, pero su ventaja frente a M2 no fue significativa (Δ −0,0021 [−0,0049; +0,0006]), así que se prefirió el modelo más simple.
- **Parámetros:** `parametros_modelo_final_M2.csv`, con mediana de imputación, media, desviación estándar, coeficiente estandarizado, coeficiente por unidad natural e intercepto. Con ellos la predicción se reproduce exactamente fuera de Python (verificado en el notebook 13):

\[
\mathrm{PD} = \frac{1}{1 + \exp\left(-\left(-5{,}267 + \sum_j \beta_j x_j\right)\right)}
\]

## 2. Predictores

| Variable | Construcción | Coef. estandarizado | OR por DE |
|---|---|---|---|
| `log_emp_previos` | log(1 + créditos previos del empleador con FINTECH) | −0,329 | 0,72 |
| `log_monto` | log del monto desembolsado | +0,239 | 1,27 |
| `edad_t0` | edad en el desembolso | −0,199 | 0,82 |
| `meses_cliente` | meses desde el primer crédito (0 si es nuevo) | −0,168 | 0,85 |
| `n_activos_t0` | créditos previos activos en t0 | −0,134 | 0,87 |
| `previo_favorable` | último cierre a término o prepago | −0,071 | 0,93 |
| `log_plazo` | log del plazo (meses) | +0,048 | 1,05 |
| `previo_adverso` | último cierre con saldo o por refinanciación | +0,045 | 1,05 |
| `log_peor_mora_previa` | log(1 + peor mora previa) | −0,031 | 0,97 |
| `tiene_historia` | tuvo al menos un crédito previo | +0,031 | 1,03 |
| `log_n_previos` | log(1 + créditos previos) | −0,016 | 0,98 |

Todos se calculan con información disponible **antes del desembolso**. Ningún IC *bootstrap* de los coeficientes excluye el 0 (`coeficientes_M2.csv`).

**Excluidos por principio:**

- género;
- identidad, LAFT/SARLAFT, geografía fina y huella digital;
- variables de política y de precio (aval, seguros, tasa);
- buró y PILA, que no existen en la muestra de desarrollo.

## 3. Datos de entrenamiento

- **Población:** 733 créditos de libranza de FINTECH desembolsados de 2022 a 2026 y maduros a 12 meses; 357 clientes; **23 incumplimientos (3,14 %)**.
- **Indeterminados:** se excluyen; las dos cotas se evalúan como sensibilidad.
- **Créditos 131 y 250:** se cuentan como incumplimientos, según la confirmación de la operación (enmienda v1.1).
- **Home Credit** (Kaggle) no entra en M2. Solo se usa como *prior* en M3 y como datos apilados en M4.

## 4. Desempeño

| Evaluación | Log loss | AUC [IC 95 %] | Pendiente de calibración | Comentario |
|---|---|---|---|---|
| Validación cruzada agrupada 5 × 20 (principal) | 0,1387 (tasa base: 0,1396) | 0,629 [0,50–0,75] | 0,62 | Mejora sobre la tasa base **no demostrable**: Δ −0,0009 [−0,0084; +0,0074] |
| Corrección de Harrell (500 réplicas) | 0,1358 | 0,675 | — | Menos conservadora que la validación cruzada |
| *Backtest* < 2025 → 2025+ (ya consultado) | 0,1076 (tasa base: 0,1066) | 0,41 [0,05–0,86] | −0,46 | 5 eventos; **no discrimina** en 2025+ |

**Bandas A–E** (límites relativos a la tasa base *p* = 3,14 %, predicciones fuera de pliegue):

| Banda | Regla | Créditos | Mora observada [IC 95 %] |
|---|---|---|---|
| A | < 0,5*p* | 40 | 5,0 % [1,4–16,5] |
| B | 0,5*p* – *p* | 402 | 1,7 % [0,8–3,6] |
| C | *p* – 2*p* | 254 | 4,7 % [2,7–8,1] |
| D | 2*p* – 4*p* | 37 | 5,4 % [1,5–17,7] |
| E | ≥ 4*p* | 0 | — |

Las bandas de M2 **no son monótonas** (prueba de tendencia, p = 0,06). Las de M3 sí lo son (p = 0,003; `../fase5/bandas_A_E.csv`).

## 5. Uso previsto y uso no previsto

**Previsto:**

- **apoyo al analista** para ordenar las solicitudes de libranza por riesgo relativo, en bandas amplias (A+B frente a C+D);
- **fijar condiciones del crédito** según la banda: exigir aval, limitar el monto o ajustar el precio;
- **punto de partida del aprendizaje incremental** (Fase 6).

**No previsto:**

- **rechazo automático** por un umbral de PD: en la Fase 5, ningún corte mejora el margen fuera de la muestra;
- **cálculo de provisiones regulatorias**: no reemplaza el modelo de referencia de la SFC;
- **otros productos** (consumo no libranza) u otras entidades;
- **calificar a quien no tiene empleador registrado** con FINTECH.

## 6. Limitaciones conocidas

1. **Pocos eventos.** Con 23, la muestra sostiene de 0,7 a 2 parámetros efectivos (Riley et al., 2020). La penalización comprime las PD (máximo de 9,6 % fuera de pliegue), y ninguna banda llega a E.
2. **Inestabilidad temporal.** Las relaciones univariadas cambian de signo entre cohortes (figura M12). El monto, la señal más regular antes de 2025, se invierte en 2025+. Sin la cohorte 2022, la señal desaparece.
3. **Sesgo de selección.** El modelo solo ve créditos aprobados. La inferencia de rechazados (k = 1–3) no cambia el ordenamiento, pero el nivel de PD de la población que solicita es incierto (3,2–4,6 %).
4. **Calibración.** Solo es verificable por debajo de 5 % de PD, y el modelo sobrestima la tasa de 2025+ (3,0 % predicha frente a 2,1 % observada).
5. **Pérdida esperada.** PD × LGD × monto subestima en cerca de 27 % la pérdida realizada, porque los incumplimientos se concentran en créditos grandes.

## 7. Consideraciones éticas y de privacidad

- **Ley 1581 de 2012.** El modelo y esta ficha contienen solo parámetros y agregados. Ninguna tabla fuera de `_privado/` tiene filas de clientes.
- **Género.** No se usa como predictor ni para estratificar. Por decisión del autor, no hay auditoría de equidad por género. Queda como limitación: no se puede descartar un efecto indirecto a través de variables correlacionadas, como la edad o el empleador.
- **Experiencia del empleador.** Es la señal más fuerte. Penaliza de hecho a los trabajadores de empresas nuevas en el convenio, un efecto que la operación debe conocer y decidir si acepta.

## 8. Monitoreo y actualización (detalle en la Fase 6)

- **Recalibrar el intercepto** a la tasa reciente antes de usar el modelo.
- **Seguir por cohorte trimestral:**
  - el PSI de los predictores;
  - la tasa observada por banda;
  - el signo y la magnitud de los coeficientes reestimados.
- **Disparadores de reentrenamiento:**
  - PSI > 0,25 en monto o en experiencia del empleador;
  - cambio de signo sostenido en dos trimestres;
  - tasa observada de la banda C+D por debajo de la de A+B.
- **Actualización conservadora:** un *prior* centrado en el modelo vigente (la lógica de M3), en lugar de un reajuste libre.
