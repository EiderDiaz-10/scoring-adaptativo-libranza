"""Monitoreo mensual (EventBridge): estabilidad del puntaje (PSI por bandas) y desempeño con los desenlaces registrados."""
import json, math, os, datetime
from comun import tabla, ahora

from comun import CARPETA_MODELO
_M = json.loads((CARPETA_MODELO / "modelo.json").read_text(encoding="utf-8"))
# distribución de referencia de las bandas (validación del modelo); en v1 eran quintiles
ESPERADO = {b: max(v, 0.005) for b, v in _M["bandas"].get("distribucion_referencia", {b: 0.2 for b in "ABCDE"}).items()}


def _todos(t):
    if t is None:
        return []
    r = t.scan(); items = r.get("Items", [])
    while "LastEvaluatedKey" in r:
        r = t.scan(ExclusiveStartKey=r["LastEvaluatedKey"]); items += r.get("Items", [])
    return items


def _auc(y, p):
    pos = [s for s, v in zip(p, y) if v == 1]; neg = [s for s, v in zip(p, y) if v == 0]
    if not pos or not neg:
        return None
    gana = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return gana / (len(pos) * len(neg))


def handler(evento, contexto):
    hoy = datetime.date.today(); desde = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=1).isoformat()
    cal = [c for c in _todos(tabla("TABLA_CALIFICACIONES")) if str(c.get("fecha_calificacion", "")) >= desde]
    n = len(cal); obs = {b: sum(1 for c in cal if c.get("banda") == b) / n for b in "ABCDE"} if n else {}
    psi = sum((o - ESPERADO[b]) * math.log((o + 1e-6) / ESPERADO[b]) for b, o in obs.items()) if n else None
    des = {d["id_solicitud"]: int(d["y_90_12m"]) for d in _todos(tabla("TABLA_DESENLACES"))}
    todas = _todos(tabla("TABLA_CALIFICACIONES"))
    pares = [(des[c["id_solicitud"]], float(c["probabilidad_incumplimiento"])) for c in todas if c["id_solicitud"] in des]
    informe = {"fecha": ahora(), "periodo_desde": desde, "calificaciones_mes": n, "distribucion_bandas": obs,
               "PSI_bandas": psi, "alerta_PSI": psi is not None and psi > 0.25, "creditos_con_desenlace": len(pares),
               "tasa_incumplimiento_observada": (sum(y for y, _ in pares) / len(pares)) if pares else None,
               "probabilidad_media_estimada": (sum(p for _, p in pares) / len(pares)) if pares else None,
               "AUC_con_desenlaces": _auc([y for y, _ in pares], [p for _, p in pares]) if len(pares) >= 30 else None}
    bucket = os.environ.get("BUCKET_REPORTES")
    if bucket:
        import boto3
        boto3.client("s3").put_object(Bucket=bucket, Key=f"monitoreo/{hoy.isoformat()}.json",
                                      Body=json.dumps(informe, ensure_ascii=False, default=float).encode("utf-8"))
        if psi is not None:
            boto3.client("cloudwatch").put_metric_data(Namespace="FINTECH/Score", MetricData=[
                {"MetricName": "PSI_bandas", "Value": psi, "Unit": "None"}])
    return informe
