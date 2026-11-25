"""Funciones compartidas por las Lambdas del score FINTECH: respuestas HTTP, validación y DynamoDB."""
import json, os, re, datetime, hashlib
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CARPETA_MODELO = AQUI / "modelo"
CAMPOS_PERSONALES = {"nombre", "nombres", "primernombre", "segundonombre", "primerapellido", "segundoapellido", "apellido",
                     "apellidos", "documento", "identificacion", "numero_documento", "cedula", "correo", "email",
                     "telefono", "celular", "direccion", "fecha_nacimiento", "fechanacimiento"}
ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_BYTES = 10 * 1024


def respuesta(codigo, cuerpo):
    return {"statusCode": codigo, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
            "body": json.dumps(cuerpo, ensure_ascii=False)}


def leer_cuerpo(evento):
    """Devuelve (dict, error). Rechaza cuerpos vacíos, inválidos o mayores a 10 KB."""
    cuerpo = evento.get("body") or ""
    if evento.get("isBase64Encoded"):
        import base64
        cuerpo = base64.b64decode(cuerpo).decode("utf-8")
    if len(cuerpo.encode("utf-8")) > MAX_BYTES:
        return None, (413, {"error": "El cuerpo supera 10 KB."})
    try:
        datos = json.loads(cuerpo)
    except (TypeError, ValueError):
        return None, (400, {"error": "El cuerpo no es un JSON válido."})
    if not isinstance(datos, dict):
        return None, (400, {"error": "El cuerpo debe ser un objeto JSON."})
    return datos, None


def quitar_personales(datos):
    """Descarta cualquier campo de identificación o contacto. Devuelve (datos_limpios, nombres_descartados)."""
    fuera = sorted(k for k in datos if k.lower() in CAMPOS_PERSONALES)
    return {k: v for k, v in datos.items() if k.lower() not in CAMPOS_PERSONALES}, fuera


def a_dynamo(obj):
    """DynamoDB no acepta float: se convierte a Decimal."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def huella_modelo():
    return hashlib.sha256((CARPETA_MODELO / "modelo.json").read_bytes()).hexdigest()[:16]


_tablas = {}
def tabla(nombre_env):
    """Tabla DynamoDB indicada por la variable de entorno; None si no está configurada (pruebas locales)."""
    nombre = os.environ.get(nombre_env)
    if not nombre:
        return None
    if nombre not in _tablas:
        import boto3
        _tablas[nombre] = boto3.resource("dynamodb").Table(nombre)
    return _tablas[nombre]
