"""Evaluación financiera de la Fase 5 (protocolo v1.1, sección 10).

Supuestos explícitos (todos se repiten en el notebook 14):
- EAD = monto desembolsado (cota superior: al incumplir, el saldo es menor).
- LGD por escenario {25; 45; 65 %} y, además, una LGD observada con los pagos posteriores al incumplimiento.
- Ingreso = intereses de los primeros 12 meses (mismo horizonte que la PD) de un crédito de cuota fija,
  netos de un costo de fondeo hipotético. No se cuentan comisiones, seguros ni estudio de crédito.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import io_datos

MES = 30.44
LGD_ESCENARIOS = {"LGD 25 %": 0.25, "LGD 45 %": 0.45, "LGD 65 %": 0.65}
BANDAS = ["A", "B", "C", "D", "E"]
LIMITES_RELATIVOS = [0.5, 1.0, 2.0, 4.0]       # múltiplos de la tasa base p


def lgd_observada(eventos: pd.DataFrame) -> pd.DataFrame:
    """LGD de cada incumplimiento según los pagos en efectivo registrados después de la fecha de 90+.

    Exposición al incumplimiento: saldo de capital del último cierre de mes anterior a esa fecha.
    Recuperación: pagos activos posteriores, sin descontar y descontados a la tasa pactada.
    El saldo trasladado a una refinanciación no cuenta como recuperado. La LGD se acota a [0, 1]
    porque los pagos incluyen intereses y gastos de mora.
    """
    tp = io_datos.leer_tabla("transaccionpago", ["credito_id", "fechapago", "valor", "estado"])
    sm = io_datos.leer_tabla("saldomesames", ["credito_id", "fecha_cierre_mes", "saldo"])
    tp = tp[tp["estado"] == "ACTIVO"].assign(cid=io_datos.llave(tp["credito_id"]), f=io_datos.fecha(tp["fechapago"]),
                                             v=io_datos.numero(tp["valor"]))
    sm = sm.assign(cid=io_datos.llave(sm["credito_id"]), f=io_datos.fecha(sm["fecha_cierre_mes"]),
                   s=io_datos.numero(sm["saldo"])).sort_values("f")
    corte = sm["f"].max()
    filas = []
    for _, r in eventos.iterrows():
        fd = pd.Timestamp(r["t0"]) + pd.Timedelta(days=float(r["dias_hasta_90"]))
        s = sm[(sm["cid"] == r["cid"]) & (sm["f"] <= fd)]
        ead = float(s["s"].iloc[-1]) if len(s) else float(r["monto"])
        p = tp[(tp["cid"] == r["cid"]) & (tp["f"] > fd)]
        meses = (p["f"] - fd).dt.days.to_numpy() / MES
        desc = float(np.sum(p["v"].to_numpy() / (1 + r["tasa_mensual"] / 100) ** meses))
        rec = float(p["v"].sum())
        filas.append({"cid": r["cid"], "grupo_cliente": r["grupo_cliente"], "anio_cohorte": r["anio_cohorte"],
                      "cierre_v2": r["cierre_v2"], "monto": float(r["monto"]), "ead_incumplimiento": ead,
                      "recuperado": rec, "recuperado_descontado": desc,
                      "lgd": float(np.clip(1 - rec / ead, 0, 1)), "lgd_descontada": float(np.clip(1 - desc / ead, 0, 1)),
                      "meses_observados": (corte - fd).days / MES})
    return pd.DataFrame(filas)


def suma_saldos_12m(monto, tasa_mensual_pct, n_cuotas) -> np.ndarray:
    """Suma de los saldos al inicio de cada uno de los primeros min(12, n) meses (cuota fija)."""
    P = np.asarray(monto, float)
    r = np.asarray(tasa_mensual_pct, float) / 100
    n = np.asarray(n_cuotas, float)
    cuota = P * r / (1 - (1 + r) ** -n)
    total, saldo = np.zeros_like(P), P.copy()
    for m in range(1, 13):
        vivo = m <= n
        total += np.where(vivo, saldo, 0)
        saldo = np.where(vivo, saldo * (1 + r) - cuota, saldo)
    return total


def ingreso_12m(D: pd.DataFrame, costo_fondeo_mensual: float) -> np.ndarray:
    """Intereses de 12 meses netos del costo de fondeo, si el crédito no incumple."""
    S = suma_saldos_12m(D["monto"], D["tasa_mensual"], D["n_cuotas"])
    return (D["tasa_mensual"].to_numpy(float) / 100 - costo_fondeo_mensual) * S


def bandas(p, base: float) -> np.ndarray:
    """Banda A–E por límites de PD relativos a la tasa base de la cartera."""
    return np.array(BANDAS)[np.searchsorted(np.array(LIMITES_RELATIVOS) * base, np.asarray(p), side="right")]


def limites_bandas(base: float) -> pd.DataFrame:
    lim = [0.0] + [m * base for m in LIMITES_RELATIVOS] + [1.0]
    return pd.DataFrame({"banda": BANDAS, "pd_desde": lim[:-1], "pd_hasta": lim[1:],
                         "regla": ["< 0,5p", "0,5p – p", "p – 2p", "2p – 4p", "≥ 4p"]})
