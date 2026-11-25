# Protocolo de análisis preespecificado — tesis v2

**Autor:** Eider Johan Díaz Berrío · **Asesor:** Juan Alejandro Peña Palacio · MCDA, Universidad EAFIT
**Versión:** 1.1 · **Fecha de congelamiento:** 15 de noviembre de 2026, antes de ajustar cualquier modelo (la fecha la certifica el *commit* de git).
**Estado:** v1.0 aprobada el 15-nov-2026. La versión 1.1 precisa y amplía la v1.0 **antes de ver cualquier resultado de modelos**; los cambios y su motivo están en `enmienda_v1.1.md`. Donde las dos versiones difieren, rige la 1.1.

Escribo este protocolo antes de modelar para que las decisiones metodológicas no dependan de los resultados. Con tan pocos incumplimientos en libranza, cualquier elección hecha después de ver métricas puede producir un resultado optimista que no se reproduce. Lo que no esté aquí y se haga después lo voy a reportar como análisis exploratorio, no confirmatorio.

## 1. Pregunta y objetivos

- **Objetivo primario.** Estimar la probabilidad de que un crédito de libranza llegue a **90 o más días de mora en los 12 meses siguientes al desembolso**, con información disponible en la fecha de solicitud (t0), y medir su desempeño fuera de muestra con incertidumbre honesta.
- **Objetivos secundarios.**
  1. Saber si usar Home Credit como información previa (*prior*) mejora la calibración o la discriminación frente a un modelo que solo usa datos propios.
  2. Aprovechar los créditos con ventana inmadura mediante un modelo de supervivencia.
  3. Revisar la sensibilidad a la definición del evento y al tratamiento de los indeterminados.
  4. Traducir los resultados a decisiones de negocio y a un protocolo de reentrenamiento.

## 2. Población y unidad de análisis

- **Unidad:** el crédito. Un cliente puede tener varios créditos, así que toda inferencia respeta el agrupamiento por cliente.
- **Fuente:** export de FINTECH del 2026-10-08. La fecha de corte efectiva es la del último pago registrado.
- **Población primaria:** créditos de **libranza** (tipos *Libranza* y *Libranza con prenda*) no anulados, con ventana de 12 meses madura, que no son indeterminados y cuya cohorte no es 2021.
- **Población de supervivencia:** todos los créditos de libranza no anulados (cohortes 2022 en adelante). Los inmaduros entran como censurados.
- La construcción, el embudo y los conteos están en `notebooks/02_objetivo_y_poblacion.ipynb`.

## 3. Variable objetivo

- **Primaria:** `y_90_12m = 1` si el máximo de días de mora (DPD) reconstruido día a día, con imputación FIFO, es **≥ 90** dentro de los 12 meses desde el desembolso. El texto de la tesis usará exactamente "90 días o más" para que coincida con el código. Responde a la definición de incumplimiento en consumo de la SFC (Circular Básica Contable y Financiera, Capítulo II).
- **Secundarias (sensibilidad):** `y_60_12m` (≥ 60 en 12 meses) y `y_30_6m` (≥ 30 en 6 meses).
- **Supervivencia:** tiempo desde el desembolso hasta el primer día con DPD ≥ 90. La observación se censura en el fin de la variante A: fecha de corte, refinanciación o último pago.
- **Indeterminados** (cierre con saldo y sin crédito posterior del mismo cliente): se excluyen del análisis primario. Reporto cotas de la tasa (indeterminado = no evento / según su mora observada / evento) y, en la Fase 4, las mismas cotas sobre las métricas del modelo. Los créditos 131 y 250 quedan marcados para verificación con la operación. Solo se reetiquetan con evidencia documental.

## 4. Predictores

- Solo variables conocidas en t0 (o, para el buró, consultadas antes del desembolso). La lista y la auditoría de fugas están en `notebooks/03_dataset_analitico.ipynb`.
- **Excluidas por principio:** identidad, listas restrictivas (LAFT/SARLAFT), **género** (decisión 6), geografía fina, variables de huella digital sintéticas o sorteadas, y cualquier variable que se actualiza después de t0 (estado, categoría actual, saldos, marca de refinanciación).
- **Selección:** por conocimiento del dominio, antes de ver la asociación con el evento en validación. Defino un conjunto núcleo de 8 a 12 variables con signo esperado al cerrar la Fase 2. Ninguna selección automática por p-valor fuera del pliegue.
- **Transformaciones con estado** (percentiles, imputación, estandarización, WoE): se ajustan **dentro de cada pliegue de entrenamiento** con `Pipeline` de scikit-learn.

## 5. Esquema de validación

1. **Principal: validación cruzada repetida, agrupada por cliente y anidada.**
   - Pliegue externo: `StratifiedGroupKFold` con 5 pliegues por cliente, **repetido 20 veces** con semillas derivadas de 20261115.
   - Pliegue interno: `StratifiedGroupKFold` de 3 pliegues para hiperparámetros, solo sobre el entrenamiento externo.
   - Todo el preprocesamiento se ajusta dentro del pliegue. Ningún cliente aparece en entrenamiento y validación a la vez (lo verifica una prueba automática).
   - Las métricas se calculan sobre las predicciones fuera de pliegue agregadas por repetición. La incertidumbre se resume con la distribución entre repeticiones y con *bootstrap* por cliente (2.000 réplicas).
2. **Secundario: *backtest* temporal.** Entrenar con cohortes < 2025 y evaluar en 2025+. Lo reporto con transparencia como un conjunto **ya consultado en la v1**, no como prueba ciega.
3. **Corrección del optimismo** de Harrell con 500 réplicas *bootstrap* por cliente para el modelo seleccionado.
4. **Opcional:** origen móvil trimestral (*walk-forward*) como análisis descriptivo de estabilidad.

## 6. Modelos (lista cerrada)

| Código | Modelo | Hiperparámetros explorados (pliegue interno) | Obligatorio |
|---|---|---|---|
| M0 | Tasa base (nulo) y regla de políticas vigente | — | Sí |
| M1 | *Scorecard* WoE + logística, 5 a 8 variables | Número de intervalos ∈ {3, 4, 5} | Sí |
| M2 | Logística penalizada solo con FINTECH (L2, L1, *elastic net*) y Firth | C ∈ 10^{-3..1} (7 valores); l1_ratio ∈ {0,25; 0,5; 0,75} | Sí |
| M3 | Logística con Home Credit como información previa (*prior* informativo / *offset*) | Escala del *prior* τ ∈ {0,25; 0,5; 1; 2; 4} | Sí |
| M4 | Configuración v1 (apilado con peso 20 % e indicador de fuente) | Fija, para continuidad | Sí |
| M5 | Árboles poco profundos y monótonos (LightGBM / EBM) | Profundidad ∈ {1, 2}; árboles ∈ {50, 100, 200}; tasa ∈ {0,05; 0,1} | No |
| M6 | Supervivencia: Cox penalizado o logística de tiempo discreto | Penalización ∈ 10^{-2..1} | Sí |
| M7 | Objetivos auxiliares 60+/12m y 30+/6m | Igual que M2 | No |

Los hiperparámetros **no** se ajustan en Home Credit. No se usa SMOTE ni sobremuestreo: dañan la calibración, como ya mostró la ablación de la v1.

## 7. Métricas

- **Primaria:** *log loss* y **Brier escalado** (1 − Brier/Brier del modelo nulo), porque el uso es estimar una probabilidad.
- **Co-primaria:** AUC (C-estadístico).
- **Secundarias:** PR-AUC frente a la prevalencia, KS, calibración (intercepto y pendiente, ICI, E50/E90, curva *loess* con banda), análisis de curva de decisión (*net benefit*) en el rango de umbrales de negocio.
- Toda métrica se reporta con IC 95 %.

## 8. Regla de selección del modelo

1. Se descartan los modelos con pendiente de calibración fuera de [0,6; 1,4] en la validación principal.
2. Entre los restantes, elijo el modelo con **menor *log loss***.
3. Si otro modelo más simple (menos parámetros efectivos, en el orden M1 < M2 < M3 < M6 < M5) tiene una diferencia de *log loss* cuyo IC 95 % *bootstrap* pareado por cliente incluye el 0, **prefiero el más simple**.
4. El AUC se usa como desempate y como chequeo de sentido, nunca como único criterio.
5. Las comparaciones pareadas frente a M1 y M2 se corrigen por comparaciones múltiples (Holm).

## 9. Análisis de sensibilidad preespecificados

- Definición del evento (60+/12m, 30+/6m, 90+/12m variante B).
- Indeterminados (tres escenarios de la sección 3).
- Exclusión de la cohorte 2022 (cohorte de arranque, con la tasa más alta).
- Peso o escala de Home Credit (curva de 0 a 50 % para M4 y de τ para M3).
- Imputación: casos completos frente a indicadores de faltante con imputación simple frente a MI dentro del pliegue.
- Ventana de la regla D4 de refinanciación no enlazada (−7/+30 y −30/+60 días).

## 10. Tamaño muestral y potencia

Los criterios de Riley et al. (2020) y la potencia para diferencias de AUC (Hanley y McNeil, 1982) se calculan en `notebooks/04_tamano_muestral_y_potencia.ipynb` con los conteos de la Fase 1. El anexo A resume los resultados. Lo que los números implican para el diseño:

- No es posible estimar con datos propios un modelo de más de unos pocos parámetros sin contracción fuerte. Por eso se usan penalización e información previa externa.
- Las diferencias de AUC entre modelos menores que la mitad del ancho del IC no se interpretarán como mejoras.

## 11. Qué **no** se hará

- No se vuelve a "evaluar una vez más" el conjunto 2025+ para elegir modelo.
- No se cambian el evento, la población ni la regla de selección después de ver resultados de validación sin dejarlo registrado como desviación del protocolo, con su fecha.
- No se usa el género ni como predictor ni para estratificar el modelo. La auditoría de equidad con género queda pendiente de autorización (D6 del plan).

## Anexo A — Resultados (notebook 04, ejecutado antes de modelar)

Población primaria: 731 créditos y 21 eventos 90+/12m (60+/12m: 27 eventos; 30+/6m: 62 eventos en 788 créditos).

| Objetivo | AUC anticipado | Parámetros máximos (S ≥ 0,9) |
|---|---|---|
| y_90_12m | 0.65 | 0.7 |
| y_90_12m | 0.70 | 1.2 |
| y_90_12m | 0.75 | 2.0 |
| y_60_12m | 0.65 | 0.9 |
| y_60_12m | 0.70 | 1.6 |
| y_60_12m | 0.75 | 2.6 |
| y_30_6m | 0.65 | 1.9 |
| y_30_6m | 0.70 | 3.4 |
| y_30_6m | 0.75 | 5.6 |

Tamaño mínimo (Riley) para 90+/12m con AUC anticipado de 0,70:

| Parámetros | n mínimo | eventos mínimos | n disponible |
|---|---|---|---|
| 5 | 2957 | 85 | 731 |
| 10 | 5913 | 170 | 731 |
| 20 | 11825 | 340 | 731 |

Potencia para el AUC con el evento primario (Hanley y McNeil; diferencia entre modelos con r = 0,5):

| AUC | IC 95 % | Diferencia mínima detectable |
|---|---|---|
| 0.60 | 0.47–0.73 | 0.186 |
| 0.65 | 0.52–0.78 | 0.185 |
| 0.70 | 0.57–0.83 | 0.181 |
| 0.75 | 0.63–0.87 | 0.175 |

**Implicación para el diseño:** los datos propios sostienen a lo sumo uno o dos parámetros sin contracción fuerte. Por eso se usan penalización, información previa de Home Credit y objetivos auxiliares, y las comparaciones entre modelos se leen con sus IC, no por el valor puntual.
