# Modelo adaptativo de evaluación de riesgo crediticio en fintech

Código, protocolo, notebooks y resultados agregados del trabajo de grado *Modelo adaptativo de evaluación de riesgo crediticio en fintech mediante formularios digitales estructurados, conjuntos de datos públicos y aprendizaje incremental*.

- **Autor:** Eider Johan Díaz Berrío
- **Asesor:** Juan Alejandro Peña Palacio
- **Programa:** Maestría en Ciencia de los Datos y Analítica, Universidad EAFIT (2026)

La entidad del caso de estudio es una fintech colombiana de crédito de libranza y aparece de forma anónima.

## Qué hay y qué no hay

Este repositorio **no contiene datos**. La base de la entidad tiene datos personales (Ley 1581 de 2012) y no se publica; Home Credit Default Risk se descarga de Kaggle con su propia licencia. Por eso los notebooks están guardados **con sus salidas**, para que se puedan leer sin ejecutarlos, pero no se pueden volver a ejecutar sin los datos.

| Carpeta | Contenido |
|---|---|
| `protocolo/` | Plan de análisis escrito antes de modelar y sus enmiendas fechadas (v1.1, v1.2 y v1.3) |
| `src/tesis_v2/` | Código compartido: evento, diseño sin fuga, modelos, métricas, evaluación financiera y componente adaptativo |
| `notebooks/` | Los 16 notebooks de las seis fases, ejecutados |
| `tests/` | 10 pruebas automáticas contra fugas de información; usan datos simulados y sí se pueden ejecutar |
| `resultados/` | Tablas agregadas (CSV), informes por fase y ficha del modelo |
| `figuras/` | Figuras de cada fase, con su catálogo |
| `evidencias/` | Registro de cada notebook: semilla, versiones y huellas de los insumos |
| `despliegue/` | Servicio de calificación en AWS (plantilla SAM, funciones Lambda, pruebas), librería de calificación y modelo exportado |

## Resultado principal

La población primaria tiene 733 créditos de libranza y 23 incumplimientos (90 días o más de mora en los 12 meses siguientes al desembolso). Se compararon once modelos con validación cruzada 5 × 20 agrupada por cliente.

- El modelo elegido por la regla preespecificada es una regresión logística con penalización L2 (M2): AUC 0,63 [0,50; 0,75].
- **Su mejora frente a predecir la tasa base no es demostrable**, su señal depende de la cohorte 2022 y no se sostiene en los créditos de 2025 en adelante.
- Usar Home Credit como información previa (M3) da el menor log loss, sin diferencia significativa frente a M2.
- En la simulación del componente adaptativo, ninguna estrategia de actualización mejora de forma demostrable al modelo congelado ni supera a la tasa base.
- La pérdida observada al incumplir es de 46 % por crédito y baja de 62 % a 15 % cuando hay aval.

El aporte del trabajo está en el diseño (tamaño muestral calculado antes de modelar, validación sin fuga, regla de selección por parsimonia) y en una lectura de los resultados que no va más allá de lo que permiten 23 eventos.

## Cómo leerlo

1. `protocolo/plan_analisis.md` y las enmiendas, en orden.
2. Los notebooks, del 01 al 16. Cada uno abre con su objetivo y cierra con sus conclusiones.
3. `resultados/fase4/tabla_unica_resultados.csv` para la comparación de modelos y `resultados/fase6/informe_fase6.md` para el componente adaptativo.

## Cómo ejecutar lo que se puede ejecutar

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests
```

Las versiones están fijadas (Python 3.14, scikit-learn 1.8.0, pandas 3.0.0, numpy 2.4.2). El archivo `requirements.txt` incluye `appnope`, que solo existe en macOS; en Linux hay que quitar esa línea. Con otras versiones de las librerías, las cifras de los modelos que eligen hiperparámetros en un pliegue interno cambian en la segunda o tercera decimal (ver `protocolo/enmienda_v1.3.md`).

Con los datos en su lugar, `python correr_todo.py` ejecuta los 16 notebooks en orden. La semilla global es 20261115.

## Servicio en AWS

`despliegue/aws/` contiene la infraestructura como código de un servicio sin servidor: una API con clave de acceso, una función que califica con el modelo M2, una que registra el desenlace, dos tablas y una función mensual de monitoreo. El servicio se desplegó y se verificó de punta a punta con solicitudes ficticias el 15 de noviembre de 2026. **No está conectado al formulario de la entidad ni recibe solicitudes reales.**

El modelo exportado (`despliegue/artefactos/modelo/modelo.json`) solo contiene parámetros: medianas, medias, desviaciones, coeficientes y cortes de las bandas.

## Diferencias con el repositorio de trabajo

Para publicarlo se preparó una copia del repositorio de trabajo, sin volver a ejecutar nada:

- Se reemplazó el nombre de la entidad por «fintech» en textos, variables, nombres de archivos y de recursos. El servicio desplegado conserva los nombres originales.
- Se retiró una salida del notebook 02 que mostraba filas de créditos individuales, y la figura E13 con su salida en el notebook 07, porque su título nombraba a la entidad.
- Se quitaron las rutas del computador del autor de las salidas de los notebooks.
- No se incluyen los archivos de Excel ni los PDF de las figuras; los CSV y los PNG equivalentes sí están.
- El historial de este repositorio empieza en la publicación. El historial original, que registra el orden en que se escribió el protocolo y se ajustaron los modelos, lo conserva el autor.

## Uso de inteligencia artificial

Se usó un asistente de IA generativa (Claude, de Anthropic) para programar, auditar el código y revisar la redacción. Las preguntas, el diseño, las decisiones metodológicas y la interpretación son del autor.
