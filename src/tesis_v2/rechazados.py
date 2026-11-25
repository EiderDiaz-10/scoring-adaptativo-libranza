"""Predictores en t0 de las solicitudes de libranza rechazadas (inferencia de rechazados, enmienda v1.1 §9).

Replica la lógica del notebook 03 para quien nunca recibió el crédito:
- monto y plazo de la solicitud (en libranza el plazo del plan coincide con el número de cuotas en meses);
- edad en la fecha de solicitud;
- historia del grupo de cliente con créditos desembolsados antes de t0 y su mora hasta t0 − 1 día;
- experiencia del empleador: créditos de FINTECH originados en ese empleador antes de t0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, io_datos, mora, objetivo
from .io_datos import fecha, llave, numero

MAPA_CIERRE = {"A_TERMINO": "a_termino", "PREPAGO": "prepago", "REFINANCIACION": "refinanciacion",
               "REFINANCIACION_NO_ENLAZADA": "refinanciacion", "CON_SALDO_CLIENTE_RECURRENTE": "con_saldo"}


def construir(t0_min, t0_max) -> pd.DataFrame:
    R = objetivo.cargar_y_reconstruir(guardar_series=True)
    sol, tipo, base = R["tablas"]["solicitud"], R["tablas"]["tipocredito"], R["base"]
    obj = io_datos.leer_parquet(config.PRIVADO / "objetivo_v2.parquet")
    grupos = io_datos.leer_parquet(config.PRIVADO / "grupo_cliente_v2.parquet")
    mapa_tipo = dict(zip(llave(tipo["id"]), tipo["tipocredito"].str.lower()))

    s = sol[sol["estado"].eq("RECHAZADA")].copy()
    s["t0"] = fecha(s["fechasolicitud"])
    s["cli"], s["emp"] = llave(s["cliente_id"]), llave(s["empresa_id"])
    s = s[~llave(s["tipocredito_id"]).map(mapa_tipo).str.contains("libre", na=False)]
    s = s[s["t0"].between(t0_min, t0_max)].reset_index(drop=True)
    g = dict(zip(grupos["cli"], grupos["grupo_cliente"]))
    # Un solicitante que nunca tuvo crédito no tiene grupo; recibe uno propio (negativo para no chocar).
    s["grupo_cliente"] = [g.get(c, -int(c)) for c in s["cli"]]

    d = pd.DataFrame({"grupo_cliente": s["grupo_cliente"].astype("Int64"), "t0": s["t0"],
                      "monto": numero(s["valortotal"]), "plazo_meses": numero(s["cantidadcuotas"]).astype(float)})
    nac = io_datos.leer_parquet(config.EXPORT_FINTECH / "bd_cliente.parquet", ["id", "fechanacimiento"])
    f_nac = pd.Series(fecha(nac["fechanacimiento"]).values, index=llave(nac["id"]))
    d["edad_t0"] = (s["t0"] - s["cli"].map(f_nac)).dt.days / 365.25
    d.loc[(d["edad_t0"] < 18) | (d["edad_t0"] > 80), "edad_t0"] = np.nan
    del nac, f_nac

    previos = obj[["cid", "grupo_cliente", "t_ref", "fin_obs_A", "cierre_v2"]]
    filas = []
    for i, r in d.iterrows():
        p = previos[(previos["grupo_cliente"] == r["grupo_cliente"]) & (previos["t_ref"] < r["t0"])]
        if len(p) == 0:
            filas.append({"n_creditos_previos": 0, "n_activos_t0": 0, "peor_mora_previa": np.nan,
                          "meses_desde_primer_credito": np.nan, "cierre_previo": "sin_previo"})
            continue
        dpd = [mora.max_dpd_hasta(R["series"], c, r["t0"] - pd.Timedelta(days=1)) for c in p["cid"]]
        cerrados = p[p["fin_obs_A"] < r["t0"]].sort_values("fin_obs_A")
        filas.append({"n_creditos_previos": len(p), "n_activos_t0": int((p["fin_obs_A"] >= r["t0"]).sum()),
                      "peor_mora_previa": float(np.nanmax(dpd)) if len(dpd) else np.nan,
                      "meses_desde_primer_credito": (r["t0"] - p["t_ref"].min()).days / 30.44,
                      "cierre_previo": MAPA_CIERRE.get(cerrados["cierre_v2"].iloc[-1], "otro_o_activo")
                      if len(cerrados) else "otro_o_activo"})
    d = d.join(pd.DataFrame(filas))
    emp_t0 = base[["emp", "t0"]].dropna()
    d["emp_creditos_previos"] = [float(((emp_t0["emp"] == e) & (emp_t0["t0"] < t)).sum()) if pd.notna(e) else 0.0
                                 for e, t in zip(s["emp"], s["t0"])]
    return d
