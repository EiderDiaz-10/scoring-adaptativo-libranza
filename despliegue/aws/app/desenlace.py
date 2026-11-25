"""POST /desenlace: registra los días de mora reales de un crédito (retroalimentación de la actualización por lotes; evento = 90 días o más)."""
from comun import respuesta, leer_cuerpo, a_dynamo, ahora, tabla, ID_VALIDO


def handler(evento, contexto):
    d, error = leer_cuerpo(evento)
    if error:
        return respuesta(*error)
    id_sol, dias = d.get("id_solicitud"), d.get("dias_mora_max_12m")
    if not isinstance(id_sol, str) or not ID_VALIDO.match(id_sol):
        return respuesta(400, {"error": "id_solicitud es obligatorio: hasta 64 letras, números, _ o -"})
    if isinstance(dias, bool) or not isinstance(dias, (int, float)) or dias < 0:
        return respuesta(400, {"error": "dias_mora_max_12m debe ser un número mayor o igual a 0"})
    item = {"id_solicitud": id_sol, "fecha_desembolso": d.get("fecha_desembolso"), "fecha_corte": d.get("fecha_corte"),
            "dias_mora_max_12m": dias, "y_90_12m": int(dias >= 90), "fecha_registro": ahora()}
    t = tabla("TABLA_DESENLACES")
    if t is not None:
        t.put_item(Item=a_dynamo(item))
    return respuesta(200, {"registrado": True, "id_solicitud": id_sol, "y_90_12m": item["y_90_12m"]})
