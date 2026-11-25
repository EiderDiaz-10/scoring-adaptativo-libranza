# Informe de la Fase 6 — Componente adaptativo / incremental

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Notebooks 15 y 16. Figuras I01–I04. Tablas en `p7_v2_adaptativo.xlsx`. Protocolo en `protocolo_monitoreo.md`.

## 1. Qué reformulé

Dejo de presentar el paso como "aprendizaje en línea". Lo que simulo es un **reentrenamiento por lotes** con fecha de conocimiento a 13 meses (versión 1.2, tras la auditoría): cada estrategia elige sus hiperparámetros en un pliegue interno con los datos conocidos en el corte, y la estrategia bayesiana actualiza solo con los créditos nuevos, con el posterior anterior como *prior* (factor de olvido 1.25). Comparo cinco estrategias: la tasa base conocida, M2 congelado, M2 expansivo, M2 ponderado y la actualización bayesiana.

## 2. Resultados de la simulación prequential

| Estrategia | n | Eventos | Log loss | AUC |
|---|---:|---:|---:|---:|
| bayes_secuencial | 433 | 10 | 0.1556 | 0.503 |
| estatico | 433 | 10 | 0.1336 | 0.634 |
| expansivo | 433 | 10 | 0.1257 | 0.530 |
| ponderado | 433 | 10 | 0.1256 | 0.522 |
| tasa_base | 433 | 10 | 0.1203 | 0.466 |

Comparaciones pareadas (bootstrap por cliente, 2.000 réplicas) frente al estático:

- **tasa_base**: Δ log loss = -0.0133 [-0.0361; +0.0066] (p = 0.221); Δ AUC = -0.168 [-0.390; +0.037] (p = 0.119).
- **expansivo**: Δ log loss = -0.0079 [-0.0220; +0.0042] (p = 0.249); Δ AUC = -0.104 [-0.225; +0.030] (p = 0.123).
- **ponderado**: Δ log loss = -0.0080 [-0.0226; +0.0054] (p = 0.274); Δ AUC = -0.111 [-0.240; +0.030] (p = 0.118).
- **bayes_secuencial**: Δ log loss = +0.0220 [+0.0006; +0.0480] (p = 0.045); Δ AUC = -0.131 [-0.235; -0.024] (p = 0.019).

**Lectura.** Las cifras de la tabla y de las comparaciones pareadas son las que mandan. En la ejecución con el entorno fijado (19-nov-2026, enmienda v1.3), reentrenar (expansivo o ponderado) no mejora al M2 congelado de forma demostrable, la actualización bayesiana es peor que el congelado en log loss y en AUC, y ninguna estrategia mejora a la tasa base conocida en log loss. En una ejecución anterior con otra versión de las librerías, el congelado eligió C = 2,15, quedó sobreajustado y reentrenar parecía corregirlo: con 6 eventos, esa conclusión depende de una sola elección de hiperparámetro. Hay 10 eventos de evaluación (potencia del orden de 12 % para un Δ AUC de 0,05). La simulación es exploratoria: muestra que el mecanismo funciona sin fuga, no que actualizar mejore la calibración ni la discriminación.

## 3. Disparadores

El conteo de 10 eventos nuevos y el PSI > 0,25 sobre predictores clave se habrían activado en varios orígenes (ver `resumen_disparadores.csv` e I04). El calendario trimestral es el ritmo mínimo; el PSI aporta un freno cuando la cartera cambia de composición (sobre todo el monto y la experiencia del empleador).

## 4. Potencia hacia adelante

Tasa media observada: **5.8 eventos por año** de originación.

| Δ AUC | Eventos necesarios | Adicionales | Años aprox. | Potencia actual (%) |
|---|---:|---:|---:|---:|
| 0.05 | 288 | 265 | 46.1 | 12.1 |
| 0.08 | 113 | 90 | 15.7 | 24.4 |
| 0.10 | 72 | 49 | 8.5 | 35.4 |
| 0.15 | 32 | 9 | 1.6 | 66.1 |

Para reivindicar una mejora pequeña (0,05 de AUC) hacen falta del orden de **288 eventos**. Con el ritmo actual eso son varios años de operación, o un cambio de objetivo auxiliar (30+/6m) si se acepta otra definición.

## 5. Despliegue

El servicio de AWS publica M2 desde la versión v20261115, en reemplazo del modelo de la tesis v1. Las actualizaciones siguientes usan el mecanismo de este protocolo (lotes con *prior* del modelo vigente), no un peso fijo del 20 % sobre Home Credit.

## 6. Qué podemos y qué no podemos afirmar

**Podemos afirmar**

- Que la simulación respeta la fecha de conocimiento (sin fuga de desenlaces futuros).
- Que el mecanismo bayesiano secuencial está bien definido y no cuenta dos veces los datos.
- Que la lectura de la simulación es frágil: cambia con la elección del hiperparámetro del modelo congelado.
- Que el PSI y el conteo de eventos son disparadores operativos verificables.
- Que la potencia hacia adelante cuantifica cuántos eventos harían falta para detectar una mejora.

**No podemos afirmar**

- Que algún modelo, adaptado o no, mejore a la tasa base conocida en log loss.
- Que adaptar mejore la calibración o la discriminación: reentrenar no difiere del congelado de forma demostrable y la actualización bayesiana es peor.
- Que el componente sea "aprendizaje en línea".

## 7. Implicación para el documento de tesis

La adaptación se presenta como **protocolo de gobierno con evidencia de simulación exploratoria**: con los eventos actuales no demuestra mejora frente al modelo congelado ni supera a la tasa base.
