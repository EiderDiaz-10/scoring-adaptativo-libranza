# Enmienda v1.2 al protocolo de análisis

**Fecha:** 15 de noviembre de 2026, después de la auditoría externa del proyecto y antes de cerrar el documento final. **Alcance:** solo la Fase 6 (componente adaptativo) y el despliegue. No cambia el evento, la población, la validación principal, la regla de selección ni ningún resultado de las Fases 1 a 5.

Esta enmienda es una **desviación registrada** después de ver resultados de la Fase 6 (sección 11 del protocolo). La motivan dos errores de diseño que encontró la auditoría, no los resultados:

## 1. Doble conteo en la actualización bayesiana

- **Problema.** En la versión 1.1, cada actualización reajustaba el modelo con *todos* los créditos conocidos y, además, con un *prior* centrado en el modelo anterior, que ya se había estimado con esos mismos créditos. Los datos antiguos contaban dos veces y el modelo quedaba anclado de más.
- **Corrección.** La verosimilitud de cada actualización usa solo los créditos cuyo desenlace se conoció desde la actualización anterior. El *prior* es el posterior anterior: media y varianza de Laplace (diagonal) de intercepto y coeficientes, con la varianza multiplicada por un **factor de olvido de 1,25**, fijado antes de correr. La estandarización queda fija desde el primer ajuste. El primer modelo es M3 (prior de Home Credit) con τ elegido en un 3-fold interno agrupado.
- **Sensibilidad.** Factores de olvido 1,0; 2,0 y 4,0 (registrados en el informe de la Fase 6).

## 2. Hiperparámetros elegidos con información futura

- **Problema.** La versión 1.1 fijaba C = 0,1 (M2) y τ0 = 0,25 (M3) con los resultados de la Fase 4, que usaron los 733 créditos, incluido el periodo que la simulación evalúa.
- **Corrección.** En cada ajuste, C (estrategias estática, expansiva y ponderada) y τ (primer ajuste bayesiano) se eligen con un 3-fold interno agrupado por cliente usando solo los créditos conocidos en ese corte.

## 3. Referencia adicional

Se agrega la estrategia **tasa base conocida** (predice la tasa observada en los créditos conocidos en el corte), que faltaba como referencia natural en la simulación.

## 4. Despliegue

Con autorización del autor (15-nov-2026), el servicio de AWS reemplaza el modelo v20261107 (tesis v1) por **M2 (v20261115)**, el modelo elegido por la regla preespecificada. Solo se publican parámetros, sin datos personales (Ley 1581).

## 5. Lectura

La Fase 6 se reporta como **exploratoria**: con 10 eventos de evaluación ninguna diferencia de AUC es concluyente y ninguna estrategia demuestra superar a la tasa base conocida.
