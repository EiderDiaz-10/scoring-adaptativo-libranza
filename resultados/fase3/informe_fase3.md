# Informe de la Fase 3 — Variables, diseño sin fuga y partición

Tesis v2 · Eider Johan Díaz Berrío · 15-nov-2026. Notebook 08 (`08_variables_y_particion.ipynb`), módulos `src/tesis_v2/diseno.py`, `modelos.py`, `metricas.py` y `contexto.py`, y pruebas `tests/test_diseno.py`. Todas las decisiones siguen la enmienda `00_protocolo/enmienda_v1.1.md`.

## 1. Población primaria

- **Etiqueta v1.1.** Eider confirmó con la operación que los créditos 131 y 250 son incumplimientos. La población primaria queda en **733 créditos de libranza maduros a 12 meses, con 23 eventos 90+/12m** (3,14 %; IC 95 % de Wilson 2,1–4,7 %) y 357 clientes.
- **Etiqueta original de la Fase 1** (731 créditos y 21 eventos): queda como sensibilidad.
- **Poblaciones de sensibilidad** (`poblaciones.csv`): 60+/12m (29 eventos), 30+/6m (64 eventos en 790), variante B (126), indeterminados en las dos cotas, sin la cohorte 2022 (17 eventos) y la población de supervivencia (1.083 créditos 2022+, incluidos los censurados).

## 2. Predictores del núcleo (11) y exclusiones

Las variables se eligieron **por dominio, antes de ver resultados de modelos** (`predictores_nucleo.csv`):

- monto y plazo (en logaritmo);
- edad en t0;
- historia del cliente: tiene historia, número de créditos previos, meses como cliente, peor mora previa, último cierre adverso o favorable y créditos activos en t0;
- experiencia del empleador con FINTECH.

Todas se calculan con información anterior a t0. Las transformaciones con estado (mediana para imputar la edad, que falta en el 0,4 %; estandarización; WoE) se ajustan **dentro de cada pliegue**.

**Exclusiones** (`variables_excluidas.csv`), con su razón documentada:

- **`recaudo`**: indicador de época, solo entra en una sensibilidad.
- **`veces_30mas_12m` y `veces_90mas_12m`**: semántica no verificada y 0 % de disponibilidad en desarrollo.
- **Buró y PILA**: 0 % disponibles en desarrollo.
- **Variables de política**: aval, seguros, cobros y tipo de solicitud.
- **`tasa_mensual`**: es endógena, porque el precio se fija según el riesgo percibido.
- **Redundantes**: cuota y número de cuotas.
- **Excluidas por principio**: género, identidad, LAFT/SARLAFT, geografía y huella digital.

## 3. Información previa de Home Credit

`prior_home_credit.csv` contiene los coeficientes de Home Credit por unidad natural para las seis variables con definición equivalente, reescalados a la desviación estándar de FINTECH. Dos de ellos **contradicen el signo esperado**: `tiene_historia` es positivo y `log_plazo` es negativo. Esto se discute en la Fase 4, porque explica por qué un *prior* demasiado estrecho perjudica.

## 4. Partición

- **Validación cruzada de la selección:** 5 pliegues × 20 repeticiones con `StratifiedGroupKFold` agrupado por `grupo_cliente`.
  - Cada pliegue de prueba tiene 146–147 créditos, de 4 a 5 eventos y 70–73 clientes (`resumen_particiones.csv`).
  - Ningún cliente aparece en dos pliegues de la misma repetición.
  - La semilla es fija y la huella de las particiones queda en `_privado/particiones.json`.
- **Pliegue interno de 3 particiones agrupadas** dentro de cada entrenamiento, para los hiperparámetros.
- ***Backtest* temporal:** < 2025 frente a 2025+, declarado como ya consultado.

## 5. Pruebas anti-fuga (`tests/test_diseno.py`, 10 pruebas, todas pasan)

1. **Agrupación:** ningún cliente queda en dos pliegues.
2. **Reproducibilidad:** las particiones son las mismas con la misma semilla.
3. **Predictores fila a fila:** alterar filas de prueba no cambia los predictores de las de entrenamiento.
4. **Ajuste independiente de la prueba**, verificado para M1, M2, M3 y M5 (cuatro casos): invertir el desenlace del pliegue de prueba y triplicar su monto no cambia sus predicciones.
5. **WoE:** las tablas no usan el desenlace de la prueba.
6. **Filas auxiliares** (objetivos auxiliares, rechazados): excluyen a los clientes del pliegue de prueba (`Contexto.permitidas`).
7. **Supervivencia:** el modelo de tiempo discreto (M6) no ve a los clientes de prueba.

## 6. Criterios de aceptación del plan

| Criterio | Estado |
|---|---|
| Las pruebas anti-fuga pasan | ✔ 10/10 |
| Ningún cliente aparece en dos pliegues | ✔ verificado en las 100 particiones |
| Las particiones son reproducibles por semilla | ✔ huella registrada |

Etiqueta de git: `v2-fase3`.
