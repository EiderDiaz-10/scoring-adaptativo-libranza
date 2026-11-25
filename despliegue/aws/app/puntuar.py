"""POST /puntuar: califica una solicitud. GET /salud: versión y estado del modelo."""
import logging
from comun import respuesta, leer_cuerpo, quitar_personales, a_dynamo, ahora, huella_modelo, tabla, ID_VALIDO, CARPETA_MODELO
from scoring import Modelo

log = logging.getLogger(); log.setLevel(logging.INFO)
MODELO = Modelo(CARPETA_MODELO)                      # se carga una vez por contenedor (arranque en frío)
if MODELO.M.get("formato") == "logistica_nucleo_v2":          # M2, tesis v2
    NUMERICAS = set(MODELO.M["entradas"]["numericas"]) | {"monto"}
    CATEGORIAS = {c: set(v) for c, v in MODELO.M["entradas"]["categoricas"].items()}
else:                                                         # formato v1 (respaldo en artefactos/_v20261107)
    NUMERICAS = set(MODELO.NUM) | {"salario_mensual", "monto_desembolsado", "score_buro", "n_obligaciones_vigentes",
                                   "aperturas_6m", "valor_en_mora_pesos", "consultas_recientes", "castigos",
                                   "tiempo_diligenciamiento_seg"} | set(MODELO.BIN)
    CATEGORIAS = {c: set(MODELO.M["versiones"][0]["diseno"]["cats"][c]) for c in MODELO.CAT}
PRODUCTO = MODELO.M.get("producto")                  # el modelo solo califica este producto (libranza)


def validar(s):
    errores = []
    for k, v in s.items():
        if k in ("id_solicitud", "fecha_solicitud") or v is None:
            continue
        if k == "tipo_producto":
            if PRODUCTO and v != PRODUCTO:
                errores.append(f"el modelo solo califica créditos de {PRODUCTO}")
            continue
        if k in NUMERICAS and (isinstance(v, bool) or not isinstance(v, (int, float))):
            errores.append(f"{k} debe ser numérica")
        elif k in CATEGORIAS and v not in CATEGORIAS[k]:
            errores.append(f"{k} debe ser una de {sorted(CATEGORIAS[k])}")
        elif k not in NUMERICAS and k not in CATEGORIAS:
            errores.append(f"{k} no es una variable del modelo")
    return errores


def handler(evento, contexto):
    if evento.get("httpMethod") == "GET":
        return respuesta(200, {"estado": "ok", "modelo": MODELO.M["modelo"], "version_modelo": MODELO.M["version"],
                               "huella_modelo": huella_modelo(), "es_ensayo": MODELO.M.get("es_ensayo", False)})
    datos, error = leer_cuerpo(evento)
    if error:
        return respuesta(*error)
    datos, descartados = quitar_personales(datos)
    if descartados:
        log.warning("Se descartaron campos personales: %s", descartados)     # solo los nombres, nunca los valores
    id_sol = datos.get("id_solicitud")
    if not isinstance(id_sol, str) or not ID_VALIDO.match(id_sol):
        return respuesta(400, {"error": "id_solicitud es obligatorio: hasta 64 letras, números, _ o -"})
    errores = validar(datos)
    if errores:
        return respuesta(400, {"error": "Solicitud inválida", "detalle": errores})
    variables = {k: v for k, v in datos.items() if k not in ("id_solicitud", "fecha_solicitud", "tipo_producto")}
    r = MODELO.puntuar(variables)
    salida = {"id_solicitud": id_sol, **r}
    t = tabla("TABLA_CALIFICACIONES")
    if t is not None:
        t.put_item(Item=a_dynamo({"id_solicitud": id_sol, "fecha_calificacion": ahora(),
                                  "fecha_solicitud": datos.get("fecha_solicitud"), "variables": variables, **r}))
    return respuesta(200, salida)
