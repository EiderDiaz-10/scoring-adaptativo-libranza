"""Rutas, semilla y parámetros fijos de la tesis v2.

Todo lo que define la población, el evento o la reconstrucción de la mora vive aquí,
para que un cambio quede registrado en git en un solo lugar.
"""
from pathlib import Path

RAIZ_V2 = Path(__file__).resolve().parents[2]
PROYECTO = RAIZ_V2.parent

# Insumos (solo lectura). El export de FINTECH es el del 2026-10-08 (decisión 4 del Project).
EXPORT_FINTECH = PROYECTO / "02_datos" / "fintech" / "2026-10-08"
BURO_PILA_V0 = PROYECTO / "03_resultados" / "fase2d_resultados" / "variables_buro_pila_v0.parquet"
OBJETIVO_V1 = PROYECTO / "03_resultados" / "fase5_resultados" / "objetivo_v1.parquet"
HOME_CREDIT_MAPEADO = PROYECTO / "03_resultados" / "p3_home_credit" / "home_credit_mapeado_v1.parquet"

# Salidas
PRIVADO = RAIZ_V2 / "_privado"            # filas de clientes: nunca sale del equipo ni entra a git
RESULTADOS = RAIZ_V2 / "resultados"        # solo tablas agregadas
FIGURAS = RAIZ_V2 / "figuras"
EVIDENCIAS = RAIZ_V2 / "evidencias"

SEMILLA = 20261115

# Reconstrucción de la mora diaria (mismos valores de la v1 para poder comparar crédito a crédito)
PARAMS_MORA = {
    "TOL_ABS": 5000.0,          # COP: faltante que no genera mora (redondeos, 4x1000)
    "TOL_REL": 0.05,            # fracción de la cuota típica
    "SALDO_CUOTAS": 0.5,        # FINALIZADO con saldo > 0,5 cuota = cierre con deuda
    "PREPAGO_DIAS": 30,         # último pago > 30 días antes de la última cuota
    "PREPAGO_CUOTAS": 1.5,      # pago final >= 1,5 cuotas = cancelación anticipada
    "PREPAGO_RATIO": 0.85,      # o pagado total >= 85 % del plan
    "VENTANAS": [6, 12],
    "UMBRALES": [30, 60, 90],
}

# Regla D4 (refinanciación no enlazada) y cohortes
VENTANA_REFI = (-15, 45)
COHORTES_EXCLUIR = [2021]
COHORTE_SENSIBILIDAD = 2022

# Evento primario y secundarios (decisión 2 del Project)
EVENTO_PRIMARIO = "y_90_12m"      # máximo DPD >= 90 en los 12 meses siguientes al desembolso
EVENTOS_SECUNDARIOS = ["y_60_12m", "y_30_6m"]

# Corte del backtest temporal secundario (decisión 1)
ANIO_BACKTEST = 2025

# Créditos indeterminados con mora > 90 días pendientes de verificar con la operación
CREDITOS_VERIFICAR = [131, 250]

# Columnas que nunca pueden aparecer en una salida (Ley 1581 de 2012)
COLUMNAS_PII = {
    "primernombre", "segundonombre", "primerapellido", "segundoapellido", "identificacion",
    "numero_documento", "email", "telefono", "direccion", "expedicion", "razonsocial",
    "personacomunicacion", "correo", "cuentadestino", "hash_identifier", "parametros_entrada",
    "resultado_normalizado", "hash_consulta", "numero", "usuariolog", "fechanacimiento",
}
# Variables prohibidas como predictores (regla 6 de AGENTS.md y decisión 6)
PROHIBIDAS_MODELO = {"genero", "identificacion", "tipoidentificacion", "laft", "sarlaft"}


def asegurar_carpetas():
    fases = ["fase1", "fase2", "fase3", "fase4", "fase5", "fase6"]
    for p in [PRIVADO, EVIDENCIAS] + [RESULTADOS / f for f in fases] + [FIGURAS / f for f in fases]:
        p.mkdir(parents=True, exist_ok=True)
