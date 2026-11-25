# Enmienda v1.1 al protocolo de análisis

**Fecha:** 15 de noviembre de 2026. **Momento:** antes de ajustar o evaluar cualquier modelo (Fases 3 y 4). El *commit* que introduce este archivo precede a todos los notebooks de modelos; git lo certifica.

La v1.0 fue aprobada el 15-nov-2026. Las decisiones metodológicas abiertas las delegó Eider en la recomendación del coordinador del proyecto. Esta enmienda hace tres cosas:

- registra una corrección de la etiqueta respaldada por evidencia operativa (sección 1);
- precisa lo que la v1.0 dejaba abierto: variables, definición exacta de cada modelo y cálculo de las métricas (secciones 2 a 8);
- agrega dos análisis secundarios solicitados: inferencia de rechazados y evaluación financiera (secciones 9 y 10).

No cambia el evento primario, la validación principal ni la regla de selección.

## 1. Etiqueta primaria: reclasificación de los créditos 131 y 250

- **Motivo.** En la Fase 1 los dos créditos quedaron como indeterminados (cierre con saldo y sin crédito posterior), aunque su mora reconstruida superaba 90 días dentro de los 12 meses (113 y 218 días). La sección 3 de la v1.0 decía que "solo se reetiquetan con evidencia documental". El 15-nov-2026 **la operación de FINTECH confirmó a Eider que ambos fueron incumplimientos.** Esa es la evidencia exigida.
- **Cambio.** Ambos créditos se incluyen como elegibles con evento: `y_90_12m = 1`, `y_60_12m = 1` y `y_30_6m = 1`; su mora observada ya cumplía las tres definiciones. **La población primaria pasa a 733 créditos con 23 eventos (3,14 %)**. La población de 30+/6m pasa a 790 créditos con 64 eventos. La de supervivencia no cambia, porque ya los contaba como eventos.
- **Sensibilidad.** La etiqueta original de la Fase 1 (731 créditos, 21 eventos) pasa a ser un análisis de sensibilidad.
- **Momento.** La decisión se toma antes de ver resultados de modelos y no depende de ellos.
- Los demás 40 indeterminados conservan el tratamiento de la v1.0: excluidos en el análisis principal, con escenarios extremos como sensibilidad.
- La implementación está en `src/tesis_v2/diseno.py`, función `poblacion(...)`, parámetro `etiqueta="v1.1"` (principal) o `"original"`.

## 2. Conjunto de predictores (cierra la sección 4 de la v1.0)

Elegí las variables por dominio y por disponibilidad en t0 **en todas las cohortes**, a partir de la propuesta de la Fase 2. No usé su asociación con el evento en validación.

| Entrada del modelo | Construcción | Signo esperado | Nota |
|---|---|---|---|
| `log_monto` | log(monto) | ? | Vigilada: deriva en el tiempo (PSI mediano 0,44) |
| `log_plazo` | log(plazo en meses) | + | |
| `edad_t0` | años; mediana del pliegue si falta (3 casos) | − | |
| `tiene_historia` | 1 si tiene créditos previos | − | |
| `log_n_previos` | log(1 + créditos previos) | − | |
| `meses_cliente` | meses desde el primer crédito; 0 si es nuevo | − | |
| `log_peor_mora_previa` | log(1 + peor DPD previo); 0 si es nuevo | + | |
| `previo_adverso` | último cierre con saldo o por refinanciación | + | |
| `previo_favorable` | último cierre a término o prepago | − | |
| `n_activos_t0` | créditos previos activos en t0 | + | |
| `log_emp_previos` | log(1 + créditos previos del empleador) | − | Vigilada: crece con el calendario |

**Imputación.** Los faltantes de historia son estructurales: un cliente nuevo no tiene "peor mora previa". No se imputan; se codifican con 0 más el indicador `tiene_historia`. Por eso la imputación múltiple de la v1.0 no aplica: el único faltante real es la edad, en 3 créditos. La sensibilidad de imputación se reduce a casos completos frente a la mediana del pliegue.

### 2.1 Variables excluidas y por qué

- **`recaudo` (modalidad de recaudo).**
  - **Problema.** Su significado exacto no está documentado; Eider tampoco lo conoce con certeza. En la Fase 2 se comportó como un indicador de época:
    - el recaudo directo solo existe hasta 2023Q3;
    - tiene el PSI más alto de todas las variables (7,7);
    - dentro de 2023 su relación con el evento se invierte.
  - **Decisión.** Queda **fuera de todos los modelos principales**. Un predictor sin definición operativa no se puede mantener en producción ni defender ante un evaluador. Además, como su distribución cambió por política, el modelo aprendería la época y no el riesgo.
  - **Sensibilidad.** Agrego `recaudo_directo` al modelo M2. Si su inclusión cambia de forma material el *log loss* o los coeficientes del núcleo, lo reporto como evidencia de confusión con el tiempo, no como señal para usar.
- **`veces_30mas_12m` y `veces_90mas_12m` (buró).**
  - **Problema.**
    - Su semántica no está verificada: no sabemos si cuentan obligaciones, meses o eventos, y en la Fase 1 mostraron valores sospechosos.
    - Tienen **0 % de disponibilidad en la muestra de desarrollo** y 7,6 % en los elegibles 2025+.
  - **Decisión.** Quedan **fuera de todos los modelos**, incluido el *prior*. No las mapeo a variables de Home Credit, porque un *prior* sobre una variable de significado incierto transfiere un efecto que no sabemos a qué corresponde.
  - **Uso posterior.** Las retomo en la Fase 6 (monitoreo) cuando la operación documente su definición y existan créditos maduros con buró.
- **Resto del buró y PILA.** Excluidos por disponibilidad: 0 % en desarrollo.
- **Variables de política o de producto** (`tiene_aval`, `aval_pct`, `cobra_seguro`, `cobra_estudio`, `cobra_4x1000`, `tipo_solicitud`, `es_refinanciacion`). Cambian de forma abrupta con las decisiones de la fintech; algunas son constantes antes de 2025.
- **`tasa_mensual`.** Es precio fijado según el perfil, así que es endógena al riesgo percibido.
- **`cuota_mensual` y `n_cuotas`.** Son redundantes con monto y plazo.
- **Otras.** `monto_sobre_solicitado` tiene solo 10 % de datos, `con_prenda` 0,4 % y `sin_empleador` es constante.
- **Género, identidad, LAFT/SARLAFT y huella digital.** Excluidos por principio. **No se hará auditoría de equidad por género:** Eider decidió eliminar la variable por completo, y esto sustituye la D6 de la v1.0.

## 3. Definición exacta de los modelos (precisa la sección 6)

- **M0a, tasa base.** La predicción es la tasa de evento del pliegue de entrenamiento.
- **M0b, regla de políticas vigente.** Es un *proxy* con las reglas evaluables en t0 del diccionario de políticas:
  - P01, edad entre 18 y 72 años;
  - P15, monto entre 0,4 y 45 millones;
  - P16, plazo entre 6 y 60 meses;
  - P20, recurrente sin mora previa ≥ 30 días (umbral de reporte).

  P08 (cuota/salario) no es evaluable porque no hay salario en desarrollo. La predicción es la tasa del pliegue en cada grupo (incumple / no incumple alguna regla). Como todos los créditos ya pasaron la política, M0b mide cuánta señal residual queda en las reglas.
- **M1, *scorecard* WoE + logística.**
  - Variables: monto, plazo, edad, peor mora previa (con un intervalo propio para "sin historia"), cierre previo (sin previo / adverso / favorable / otro o activo), antigüedad como cliente (con "sin historia") y experiencia del empleador.
  - Intervalos: por cuantiles del pliegue, número ∈ {3, 4, 5} elegido en el pliegue interno.
  - WoE con suavizado de Laplace 0,5, ajustado solo con el entrenamiento.
  - Logística L2 con C = 1, fija.
- **M2, logística penalizada.** Estandarización en el pliegue.
  - El pliegue interno elige penalización ∈ {L2, L1, *elastic net* con l1_ratio ∈ {0,25; 0,5; 0,75}} y C ∈ 10^{−3…1} (7 valores en escala logarítmica).
  - **M2F (Firth)** se reporta aparte, sin hiperparámetros, y cuenta en la regla de selección con la misma complejidad que M2.
- **M3, logística con Home Credit como información previa.**
  - **Prior de los coeficientes:** β_j ~ N(μ_j, τ²) sobre la escala estandarizada del pliegue.
  - **Variables compartidas** (edad, log plazo, tiene historia, log créditos previos, meses como cliente y log peor mora previa): μ_j = β_j^HC × DE_j^FINTECH.
    - β_j^HC es el coeficiente por unidad natural de una logística ajustada en Home Credit (224.647 solicitudes, variables construidas igual que en FINTECH).
    - DE_j^FINTECH es la desviación estándar de la variable en el entrenamiento del pliegue.
  - **Variables sin equivalente:** μ_j = 0.
  - **Intercepto:** prior plano, porque la tasa base de Home Credit (9 %) no se transfiere.
  - **Escala τ ∈ {0,25; 0,5; 1; 2; 4}**, elegida en el pliegue interno.
  - **Estimación:** máximo a posteriori. Los intervalos creíbles del modelo final usan la aproximación de Laplace, que verifico con un muestreo de Metropolis.
  - **Interpretación:** con μ = 0, M3 equivale a M2-L2 con C = τ². La comparación M3 frente a M2 aísla, por tanto, el valor del centro informativo.
- **M4, configuración v1.**
  - Datos apilados: FINTECH más una submuestra fija de 40.000 registros de Home Credit (semilla del proyecto).
  - FINTECH aporta el 20 % del peso total.
  - Indicador de fuente y logística L2 con C = 1.
  - Las variables sin equivalente se fijan, en los registros de Home Credit, en la media del entrenamiento de FINTECH.
  - Curva de sensibilidad del peso de Home Credit ∈ {0; 10; 25; 50; 80 %}, donde 80 % corresponde a la v1.
- **M5, *boosting* acotado.**
  - `HistGradientBoostingClassifier` con restricciones monótonas según el signo esperado; sin restricción para el monto.
  - `min_samples_leaf` = 20 y `l2_regularization` = 1.
  - Pliegue interno: profundidad ∈ {1, 2}, árboles ∈ {50, 100, 200}, tasa ∈ {0,05; 0,1}.
  - Interpretación con SHAP.
- **M6, supervivencia en tiempo discreto.**
  - Logística sobre registros crédito-mes, con meses 4 a 12. Antes del mes 4 el evento es imposible por construcción: el primer 90+ observado ocurre el día 120.
  - Riesgo base por tramos (meses 4–6, 7–9 y 10–12).
  - Penalización L2 con C ∈ {0,01; 0,1; 1; 10}.
  - Entrenamiento: libranza 2022+, incluidos los créditos inmaduros e indeterminados como censurados, excluidos los clientes del pliegue de prueba.
  - Predicción: PD a 12 meses, PD = 1 − Π(1 − h_m), evaluada sobre la misma población primaria.
  - Como apoyo descriptivo, un Cox de riesgos proporcionales con sus *hazard ratios*.
- **M7, objetivos auxiliares.** M2-L2 entrenado con 60+/12m y, por separado, con 30+/6m, en sus propias poblaciones y sin los clientes del pliegue de prueba. Después se recalibra a 90+/12m en el entrenamiento (intercepto y pendiente sobre el logit) y se evalúa en la población primaria.

## 4. Particiones y cálculo de métricas (precisa la sección 5)

- Las particiones son las mismas para todos los modelos: `StratifiedGroupKFold` de 5 pliegues por `grupo_cliente`, 20 repeticiones, con semillas 20261115 + r. Se guardan en `_privado/particiones.json` y su resumen agregado en `resultados/fase3/`.
- **Estimación puntual:** la media, entre las 20 repeticiones, de la métrica calculada con las predicciones fuera de pliegue de cada repetición.
- **IC 95 %:** *bootstrap* percentil por cliente con 2.000 réplicas. En cada réplica se recalcula la métrica de cada repetición sobre los clientes remuestreados y se promedia.
- **Diferencias pareadas** (Δ *log loss* y Δ AUC): se calculan con las mismas réplicas. El p-valor bilateral es 2 × min(P(Δ ≤ 0), P(Δ ≥ 0)). Aplico Holm a las comparaciones frente a M1 y frente a M2.
- **Pendiente de calibración:** se mide igual, por repetición. Un modelo es elegible si su pendiente puntual está en [0,6; 1,4].
- **Referencia frente a la tasa base:** si el IC del Δ *log loss* del modelo elegido frente a M0a incluye 0, lo declaro explícitamente. En ese caso el modelo no demuestra que estime mejor la probabilidad que la tasa base, aunque discrimine.
- **Corrección del optimismo de Harrell:** 500 réplicas para el modelo elegido, repitiendo el ajuste de hiperparámetros.
- **Análisis de sensibilidad:** 5 pliegues × 10 repeticiones (menos cómputo); M2, M3 y el modelo elegido.

## 5. Candidatos de la regla de selección

Son candidatos M1, M2/M2F, M3, M6 y M5, en ese orden de complejidad. M0a y M0b son referencias. M4 se reporta por continuidad con la v1. M7 es una sensibilidad.

## 6. *Backtest* temporal

Para todos los modelos: entrenar con las cohortes < 2025 y evaluar una sola vez en 2025+, con los hiperparámetros elegidos por validación interna sobre < 2025. Lo reporto como conjunto **ya consultado en la v1**; no interviene en la selección.

## 7. Sensibilidades (amplía la sección 9)

- Etiqueta original de la Fase 1 (731/21).
- 60+/12m.
- 30+/6m.
- Variante B.
- Indeterminados como no evento y como evento.
- Sin la cohorte 2022.
- Ventanas D4 de −7/+30 y −30/+60 días.
- Casos completos.
- `recaudo` como variable adicional.
- Curvas de τ (M3) y del peso de Home Credit (M4).
- Estabilidad de la selección de variables: L1 en 500 réplicas *bootstrap* por cliente.
- Inferencia de rechazados (sección 9).

## 8. Interpretabilidad

- Coeficientes con IC por *bootstrap* por cliente: M2. Intervalos creíbles: M3.
- *Odds ratios* por desviación estándar.
- Contraste del signo observado con el esperado.
- SHAP y dependencia parcial para M5.

## 9. Inferencia de rechazados (análisis secundario, nuevo)

- **Motivo.** El rechazo de solicitudes de libranza subió de 5,5 % a 27,8 %, así que el modelo solo ve a los aprobados, una población cada vez más seleccionada.
- **Población.** Solicitudes de libranza **rechazadas** cuya fecha está en la misma ventana de originación que la población primaria. Sus predictores se construyen en t0 con la misma lógica que los de los créditos:
  - monto, cuotas y modalidad de la solicitud;
  - edad;
  - historia del grupo de cliente antes de t0;
  - experiencia del empleador.
- **Método: aumentación difusa (*fuzzy augmentation*).**
  - Cada rechazado entra dos veces: como evento con peso min(1, k·p̂) y como no evento con peso 1 − min(1, k·p̂).
  - p̂ es la predicción del modelo de aprobados ajustado en el mismo pliegue.
  - k ∈ {1; 2; 3} expresa el supuesto de que los rechazados son entre igual de riesgosos y tres veces más riesgosos de lo que el modelo ve.
- **Reporte.** Cambios en los coeficientes y en las métricas sobre los aprobados (mismas particiones; los rechazados de clientes del pliegue de prueba no entran al entrenamiento) y la PD implícita de la población que solicita (*through-the-door*).
- **Alcance.** Es un análisis de sensibilidad. El supuesto k no es verificable con estos datos.

## 10. Evaluación financiera (Fase 5)

- **Pérdida esperada:** EL = PD × LGD × EAD.
  - EAD = monto desembolsado; es una cota superior, porque al incumplir el saldo es menor.
  - LGD ∈ {25; 45; 65 %}, todos hipotéticos: no hay datos de recuperación.
- **Ingreso aproximado:** tasa mensual pactada × monto × meses esperados de vida, con supuestos explícitos.
- **Bandas A–E** por límites de PD fijados con criterio de negocio relativo a la tasa base de la cartera (*p*):
  - A < 0,5*p*;
  - B entre 0,5*p* y *p*;
  - C entre *p* y 2*p*;
  - D entre 2*p* y 4*p*;
  - E ≥ 4*p*.
- **Reporte de bandas:** la monotonía de la tasa observada por banda, con IC de Wilson.
- **Curvas** de tasa de aprobación frente a tasa de mora y frente a margen. Punto de corte con su IC *bootstrap*.
- **Comparación frente a M0b:** malos evitados y buenos rechazados, con IC.
- **Predicciones:** todo se calcula con las predicciones fuera de pliegue promediadas de la validación principal. El *backtest* 2025+ se usa solo como ilustración.
