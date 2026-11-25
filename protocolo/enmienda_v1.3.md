# Enmienda v1.3 del protocolo (19 de noviembre de 2026)

Origen: auditoría académica del 19 de noviembre de 2026. No cambia el evento, la población, los modelos, las métricas ni la regla de selección.

## 1. Semilla del optimizador saga (corrección de reproducibilidad)

**Problema.** En `src/tesis_v2/modelos.py`, la logística con elastic net (`solver="saga"`) no tenía `random_state`. Con los mismos datos de entrenamiento, dos ajustes daban probabilidades distintas (hasta 7 × 10⁻⁵) y el pliegue interno elegía configuraciones distintas en 71 de 100 pliegues externos, porque varias configuraciones quedan casi empatadas. La prueba `test_prediccion_de_prueba_no_depende_de_la_prueba[M2]` fallaba por esta causa (9 de 10 pruebas); no es una fuga, porque los datos de entrenamiento de las dos corridas de la prueba son idénticos.

**Cambio.** Se agregó `random_state=config.SEMILLA` a esa logística. Es el único cambio de código.

**Verificación (Python 3.10.12, scikit-learn 1.7.2).** Dos corridas de la validación 5 × 20 de M2 son idénticas (diferencia máxima 0; 0 elecciones distintas). AUC 0,6424 y log loss 0,1384 antes y después de fijar la semilla. Las 10 pruebas pasan.

**Efecto sobre la tesis.** Las cifras publicadas se produjeron antes de este cambio, en Python 3.14.2 y scikit-learn 1.8.0. El efecto medido de la semilla está por debajo de la cuarta decimal. Queda pendiente ejecutar `correr_todo.py` en el entorno original y confirmar que las tablas no cambian al redondeo que se reporta.

## 2. Sensibilidad al entorno (hallazgo, sin cambio de código)

Al repetir el notebook 09 en el segundo entorno con las particiones externas guardadas, M0a, M0b, M2F y M4 se reproducen exactamente. Los modelos con selección interna cambian, porque las particiones internas se regeneran y dependen de la versión de las librerías:

| Modelo | AUC tesis | AUC segundo entorno | Log loss tesis | Log loss segundo entorno |
|---|---|---|---|---|
| M1 | 0,5471 | 0,5629 | 0,15114 | 0,14850 |
| M2 | 0,6294 | 0,6424 | 0,13869 | 0,13837 |
| M3 | 0,6531 | 0,6537 | 0,13663 | 0,13657 |
| M5 | 0,6333 | 0,6325 | 0,13707 | 0,13737 |
| M6 | 0,6025 | 0,6021 | 0,14260 | 0,14291 |
| M7 60+/12m | 0,6419 | 0,6404 | 0,13893 | 0,13879 |
| M7 30+/6m | 0,6052 | 0,6072 | 0,13916 | 0,13902 |

El orden de los modelos y las conclusiones no cambian. La tesis lo declara como limitación (sección 7.8 y Anexo J). Recomendación para ejecuciones futuras: guardar también las particiones internas.

## 3. Precisiones de texto en la tesis

- Frecuencias de selección con L1: se indica que 93 %, 85 % y 84 % corresponden a C = 0,464 y se agregan las de C = 0,1 (79 %, 32 % y 20 %).
- Alcance de la preespecificación: protocolo y modelos son del mismo día; protege contra elegir entre los análisis de esta versión, no contra lo aprendido en la versión preliminar.
- Revistas Q1: 35 de 37 artículos clasificados en Scimago; las referencias posteriores no se clasificaron.

## 4. Reproducción con las versiones fijadas (19 de noviembre de 2026)

Se instaló el entorno de `requirements.txt` (Python 3.14, scikit-learn 1.8.0, pandas 3.0.0, numpy 2.4.2) en una máquina Linux, con la semilla de saga ya fijada.

- Los 11 modelos reproducen las predicciones fuera de pliegue guardadas (diferencia máxima 1,4 × 10⁻⁵ en M2; 10⁻¹³ o menos en los demás) y las mismas cifras de AUC y log loss.
- Se ejecutaron de nuevo los notebooks 01 a 11, 13, 14 y 16. De 79 archivos de resultados regenerados, 71 son idénticos byte a byte; los 8 restantes difieren en milésimas (valores p, intervalos, AUC corregido de Harrell 0,6746 frente a 0,6753). Ninguna cifra de la tesis cambia.
- Pendiente: notebooks 12 y 15 (y volver a guardar el 10 y ejecutar el 16 después del 15) en el equipo del autor: `.venv/bin/python correr_todo.py 10 12 15 16`.
- Respaldo de lo anterior: `auditoria_externa/respaldo_antes_reejecucion_20261119/`.

## 5. Ejecución completa en el equipo del autor y cambio en la fase 6 (19 de noviembre de 2026)

El autor ejecutó en su Mac los notebooks 10, 12, 15 y 16 con el entorno fijado. Con esto, los 16 notebooks quedan ejecutados con las mismas versiones.

- **Notebook 10:** sin cambios en las cifras reportadas.
- **Notebook 12 (sensibilidades):** cambios en la tercera decimal. «Sin la cohorte 2022»: AUC de M2 0,498 (antes 0,486) y Δ log loss +4,5 [−0,7; +13,4]. La conclusión no cambia.
- **Notebook 15 (simulación prequential): cambia la lectura.** La simulación anterior se había ejecutado con scikit-learn 1.7. Con 1.8.0, el pliegue interno del M2 congelado elige C = 0,464 (antes 2,15):

| Estrategia | Log loss antes | Log loss ahora | AUC antes | AUC ahora |
|---|---|---|---|---|
| Tasa base | 0,1203 | 0,1203 | 0,466 | 0,466 |
| M2 congelado | 0,1633 | 0,1336 | 0,628 | 0,634 |
| M2 expansivo | 0,1337 | 0,1257 | 0,509 | 0,530 |
| M2 ponderado | 0,1341 | 0,1256 | 0,509 | 0,522 |
| Bayesiana secuencial | 0,1556 | 0,1556 | 0,503 | 0,503 |

Frente al congelado: expansivo −0,008 [−0,022; +0,004]; ponderado −0,008 [−0,023; +0,005]; bayesiana +0,022 [+0,001; +0,048] en log loss y −0,13 [−0,24; −0,02] en AUC; tasa base −0,013 [−0,036; +0,007].

**Consecuencia.** La afirmación «actualizar corrige el sobreajuste de un modelo congelado» deja de sostenerse. La tesis reporta las cifras nuevas, declara que la simulación es frágil (con 6 eventos, una elección de hiperparámetro cambia la conclusión) y trata cada actualización como candidata frente al modelo vigente. Se corrigió el texto fijo del notebook 16 y el informe de la fase 6.

## 6. Fundamento de la etiqueta de los créditos 131 y 250 (corrección del registro)

La enmienda v1.1 dice que la operación de la entidad confirmó que los créditos 131 y 250 fueron incumplimientos. **Esa confirmación no está documentada y el autor no tiene información de la entidad sobre el desenlace final de esos dos créditos.** Se corrige el registro:

- **La etiqueta no cambia.** Ambos siguen como eventos en el análisis principal (733 créditos, 23 eventos).
- **El fundamento es la regla del evento**, no una confirmación: el evento es alcanzar 90 días o más de mora dentro de los 12 meses desde el desembolso, cualquiera sea el cierre posterior. Así se etiqueta el resto de la cartera: entre los demás eventos hay créditos que después se pagaron a término o se prepagaron. Los créditos 131 y 250 alcanzaron 113 y 218 días dentro de la ventana.
- **Aplicación uniforme.** De los 42 indeterminados de libranza, son los únicos dos con 90 días o más en la ventana (los demás quedaron por debajo de 90 días). Los otros 40 siguen excluidos, con las cotas de sensibilidad.
- **Sensibilidad.** La etiqueta original (731 créditos, 21 eventos) se sigue reportando siempre; con ella el AUC de M2 es 0,62 y la conclusión no cambia.
- **Cautela.** La mora es reconstruida a partir del plan y los pagos. El crédito 250 registra pagos por el 116 % del plan, lo que sugiere pagos aplicados tarde.

La tesis (sección 6.1, limitaciones y Anexo G) quedó redactada con este fundamento.
