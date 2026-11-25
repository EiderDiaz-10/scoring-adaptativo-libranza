"""Pruebas de los manejadores sin AWS (sin tablas configuradas). Correr: cd 06_despliegue/aws && ./empaquetar.sh && python -m pytest -q tests"""
import json, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "build_src"))
sys.path.insert(0, str(AQUI.parent.parent / "modelo_fintech"))
import puntuar, desenlace, monitoreo
from scoring import Modelo
EJEMPLO = json.loads((AQUI.parent.parent / "modelo_fintech" / "ejemplo_solicitud.json").read_text(encoding="utf-8"))
EJEMPLO = {k: v for k, v in EJEMPLO.items() if not k.startswith("_")}


def post(fn, cuerpo):
    r = fn.handler({"httpMethod": "POST", "body": json.dumps(cuerpo)}, None)
    return r["statusCode"], json.loads(r["body"])


def test_salud():
    r = puntuar.handler({"httpMethod": "GET"}, None); b = json.loads(r["body"])
    assert r["statusCode"] == 200 and b["estado"] == "ok" and b["es_ensayo"] is False


def test_solicitud_completa_igual_a_local():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-001", **EJEMPLO})
    local = Modelo(AQUI.parent.parent / "artefactos" / "modelo").puntuar(EJEMPLO)
    assert c == 200 and abs(b["probabilidad_incumplimiento"] - local["probabilidad_incumplimiento"]) < 1e-6
    assert b["banda"] in "ABCDE" and b["variables_faltantes"] == []


def test_solicitud_incompleta():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-002", "edad_t0": 30, "tipo_producto": "libranza"})
    assert c == 200 and len(b["variables_faltantes"]) >= 7 and b["banda"] in "ABCDE"


def test_categoria_invalida():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-003", "tipo_producto": "hipotecario"})
    assert c == 400


def test_tipo_invalido_y_variable_desconocida():
    assert post(puntuar, {"id_solicitud": "P4", "edad_t0": "treinta"})[0] == 400
    assert post(puntuar, {"id_solicitud": "P5", "estrato": 3})[0] == 400


def test_campos_personales_se_descartan():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-006", "nombre": "X", "documento": "1", "correo": "a@b.co", **EJEMPLO})
    assert c == 200 and "nombre" not in json.dumps(b)


def test_sin_id_y_cuerpo_grande():
    assert post(puntuar, EJEMPLO)[0] == 400
    r = puntuar.handler({"httpMethod": "POST", "body": json.dumps({"id_solicitud": "G", "x": "a" * 11000})}, None)
    assert r["statusCode"] == 413


def test_desenlace():
    c, b = post(desenlace, {"id_solicitud": "PRUEBA-001", "dias_mora_max_12m": 120})
    assert c == 200 and b["y_90_12m"] == 1
    assert post(desenlace, {"id_solicitud": "PRUEBA-001", "dias_mora_max_12m": -3})[0] == 400


def test_monitoreo_sin_tablas():
    r = monitoreo.handler({}, None)
    assert r["calificaciones_mes"] == 0 and r["PSI_bandas"] is None


def test_rechaza_otro_producto():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-LI", **{**EJEMPLO, "tipo_producto": "libre_inversion"}})
    assert c == 400 and "libranza" in " ".join(b["detalle"])


def test_cierre_previo_invalido():
    c, b = post(puntuar, {"id_solicitud": "PRUEBA-CP", **{**EJEMPLO, "cierre_previo": "desconocido"}})
    assert c == 400


def test_desenlace_umbral_90_inclusivo():
    assert post(desenlace, {"id_solicitud": "PRUEBA-90", "dias_mora_max_12m": 90})[1]["y_90_12m"] == 1
    assert post(desenlace, {"id_solicitud": "PRUEBA-89", "dias_mora_max_12m": 89})[1]["y_90_12m"] == 0


def test_bandas_monotonas_en_ejemplos():
    m = Modelo(AQUI.parent.parent / "artefactos" / "modelo")
    riesgoso = json.loads((AQUI.parent.parent / "modelo_fintech" / "ejemplo_riesgoso.json").read_text(encoding="utf-8"))
    riesgoso = {k: v for k, v in riesgoso.items() if not k.startswith("_")}
    assert m.puntuar(riesgoso)["probabilidad_incumplimiento"] > m.puntuar(EJEMPLO)["probabilidad_incumplimiento"]
