# Protocolo de monitoreo y actualización del modelo (tesis v2)

**Fecha:** 15-nov-2026 · **Modelo de referencia:** M2 (elegido) / actualización bayesiana secuencial con prior de Home Credit (M3) · **Versión desplegada en AWS:** M2, v20261115.

## 1. Qué es y qué no es este protocolo

| Concepto | Qué hago | Qué no hago |
|---|---|---|
| Reentrenamiento por lotes | Reestimo coeficientes cuando se cumple un disparador, con todos los créditos cuyo desenlace ya es conocido | Actualizar el modelo con cada crédito nuevo en tiempo real |
| Aprendizaje en línea | — | No lo implemento ni lo reivindico: con ~6 eventos/año no hay señal estable crédito a crédito |
| Fecha de conocimiento | Un crédito desembolsado en t0 entra al entrenamiento en t0 + 13 meses | Usar la etiqueta antes de que madure la ventana de 12 meses |

## 2. Indicadores que sigo cada trimestre

1. **Tasa observada por banda A–E** (límites relativos a la tasa base vigente) y monotonía.
2. **PSI** de `log_monto`, `log_emp_previos`, `edad_t0` y `log_plazo` frente a la distribución del último entrenamiento.
3. **PSI del puntaje** (PD) frente a la distribución de PD del entrenamiento.
4. **Signo de los coeficientes reestimados** (ventana expansiva de diagnóstico): cambio de signo sostenido en dos trimestres.
5. **Calibración en grande:** PD media frente a tasa observada en la cohorte más reciente con desenlace conocido.

## 3. Disparadores de reentrenamiento

Se dispara un reentrenamiento por lotes si ocurre **cualquiera** de:

| Disparador | Umbral | Justificación |
|---|---|---|
| Calendario | Cada trimestre natural | Ritmo mínimo de gobierno |
| Conteo de eventos | Cada 10 incumplimientos nuevos maduros | Acumular señal antes de mover coeficientes |
| Deriva de predictores | PSI > 0.25 en `log_monto` o `log_emp_previos` | Variables vigiladas en la ficha del modelo |
| Deriva del puntaje | PSI del PD > 0.25 | Cambio de la distribución de riesgo predicida |
| Inversión de bandas | Tasa de C+D por debajo de A+B en dos trimestres | Falla de ordenamiento de negocio |

## 4. Cómo actualizo (mecanismo M3)

1. Tomo como *prior* el **posterior del modelo vigente**: media y varianza de Laplace de intercepto y coeficientes, con la varianza multiplicada por un factor de olvido de 1.25 (fijado a priori).
2. La verosimilitud usa **solo los créditos que maduraron desde la última actualización**, para no contar dos veces los datos.
3. Estimo el MAP con esos dos elementos; el primer modelo es M3 (prior de Home Credit, τ elegido en un pliegue interno).
4. Recalibro el intercepto a la tasa reciente (calibración en grande) antes de publicar.
5. Conservo M2 estático como **testigo**: si el modelo actualizado no mejora el log loss fuera de la bolsa en la ventana de control, no lo promuevo.

## 5. Buró (`veces_30mas` / `veces_90mas`)

Quedan **fuera del modelo** hasta que la operación documente su definición y existan créditos maduros con buró observado (enmienda v1.1). En monitoreo solo los perfilo: cobertura trimestral y PSI cuando la cobertura superé el 30 %.

## 6. Despliegue AWS

- Desde la versión v20261115 la API (`06_despliegue/`) califica con **M2** (11 predictores, bandas A–E relativas a la tasa base). Reemplazó al modelo v20261107 de la tesis v1, con autorización del autor y sin subir datos personales (Ley 1581).
- Cada actualización futura se publica como un nuevo `modelo.json`; el contrato se mantiene: entrada = solicitud con sus 11 predictores, salida = PD + banda, y un endpoint de retroalimentación de mora para el lote de reentrenamiento.
- Tolerancia de reproducibilidad local frente a AWS: 1e-9 en la PD.

## 7. Criterio de éxito de una actualización

Una actualización se declara exitosa solo si, en la ventana de control posterior (créditos que maduran después del corte, sin haber entrado al entrenamiento):

- el Δ log loss frente al testigo estático es ≤ 0 (punto), **y**
- el IC 95 % bootstrap por cliente del Δ no queda enteramente por encima de 0, **o** hay al menos el número de eventos que exige la tabla de potencia de la Fase 6 para el Δ buscado.

Con menos eventos que ese umbral, la actualización se registra como **exploratoria**, no como mejora demostrada.
