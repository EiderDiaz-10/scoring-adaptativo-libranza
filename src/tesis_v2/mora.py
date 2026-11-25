"""Reconstrucción de los días de mora (DPD) diarios a partir del plan de pagos y los pagos.

Es una reimplementación auditada del método de la Fase 5 de la v1 (01_codigo/fase5_paso_a_paso.py)
con los mismos parámetros, para poder comparar crédito a crédito:

- Exigible acumulado E(d): suma de las cuotas del plan vigente (DESEMBOLSO; CREDITO si falta) con fecha <= d.
- Pagado acumulado P(d): pagos ACTIVO con valor > 0, sin duplicados exactos.
- Imputación FIFO: cada pago cubre primero la cuota más antigua.
- DPD(d) = d - fecha de la cuota más antigua no cubierta (0 si no hay cuota vencida sin cubrir).
- Tolerancia: una cuota está cubierta si el faltante es <= max(TOL_ABS, TOL_REL x cuota típica).

Fin de observación (variante A, principal): fecha de corte para activos, fecha de inicio del crédito
nuevo para refinanciaciones enlazadas y último pago para los demás cierres. La variante B extiende
hasta la fecha de corte los cierres sospechosos (con saldo, sin pagos o anticipados sin explicación).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PARAMS_MORA as P
from .io_datos import fecha, llave, numero


def preparar_base(cred: pd.DataFrame, sol: pd.DataFrame, des: pd.DataFrame, tipo: pd.DataFrame) -> pd.DataFrame:
    """Una fila por crédito no anulado con sus fechas de referencia."""
    c = cred[~cred["estado"].isin(["ANULADO", "PENDIENTE_DESEMBOLSO"])].copy()
    c["cid"], c["sid"] = llave(c["id"]), llave(c["solicitud_id"])
    c["cli"], c["emp"] = llave(c["cliente_id"]), llave(c["empresa_id"])
    c["fechainicialcredito"] = fecha(c["fechainicialcredito"])
    s = sol.assign(sid=llave(sol["id"]), fechasolicitud=fecha(sol["fechasolicitud"]))
    c = c.merge(s[["sid", "fechasolicitud", "tipo_solicitud"]], on="sid", how="left")
    c["t0"] = c[["fechasolicitud", "fechainicialcredito"]].min(axis=1)
    d = des.assign(cid=llave(des["credito_id"]), f=fecha(des["fechadesembolso"])).groupby("cid")["f"].min()
    c["fechadesembolso"] = c["cid"].map(d)
    c["t_ref"] = c["fechadesembolso"].fillna(c["fechainicialcredito"])
    c["anio_cohorte"] = c["t0"].dt.year.astype("Int64")
    mapa = dict(zip(llave(tipo["id"]), tipo["tipocredito"]))
    c["tipocredito"] = llave(c["tipocredito_id"]).map(mapa)
    c["producto"] = np.where(c["tipocredito"].str.lower().str.contains("libre"), "libre_inversion", "libranza")
    return c.reset_index(drop=True)


def plan_vigente(proy: pd.DataFrame) -> pd.DataFrame:
    pr = proy.dropna(subset=["credito_id"]).copy()
    pr["cid"], pr["ncuota"] = llave(pr["credito_id"]), numero(pr["ncuota"])
    pr = pr[pr["ncuota"] > 0]
    pr["fecha"] = fecha(pr["fecha"]).dt.normalize()
    pr["valorcuota"] = numero(pr["valorcuota"]).fillna(0)
    des = pr[pr["tipoproyeccion"] == "DESEMBOLSO"]
    sin_des = set(pr["cid"]) - set(des["cid"])
    plan = pd.concat([des, pr[(pr["tipoproyeccion"] == "CREDITO") & pr["cid"].isin(sin_des)]])
    plan = (plan.sort_values(["cid", "ncuota", "id"]).drop_duplicates(["cid", "ncuota"], keep="last")
            .sort_values(["cid", "fecha"]))
    return plan[["cid", "ncuota", "fecha", "valorcuota"]].reset_index(drop=True)


def pagos_validos(tp: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    t = tp.copy()
    t["valor"] = numero(t["valor"])
    t = t[(t["estado"] == "ACTIVO") & (t["valor"] > 0)]
    n0 = len(t)
    t = t.drop_duplicates(subset=[c for c in ["credito_id", "fechapago", "valor", "fuente", "fechalog"] if c in t])
    t["cid"], t["fecha"] = llave(t["credito_id"]), fecha(t["fechapago"]).dt.normalize()
    return t[["cid", "fecha", "valor"]].sort_values(["cid", "fecha"]).reset_index(drop=True), n0 - len(t)


def enlaces_refinanciacion(sol: pd.DataFrame, cred: pd.DataFrame) -> pd.Series:
    """Crédito anterior -> fecha de inicio del crédito nuevo que lo refinanció (enlace explícito)."""
    s = sol[sol["tipo_solicitud"].isin(["REFINANCIACION", "REFINANCIACION_ANTERIOR"]) & sol["credito_id"].notna()]
    s = s.assign(sid=llave(s["id"]), cid_old=llave(s["credito_id"]))
    c = cred.assign(sid=llave(cred["solicitud_id"]), cid_new=llave(cred["id"]),
                    fini=fecha(cred["fechainicialcredito"]))
    m = s.merge(c[["sid", "cid_new", "fini"]], on="sid")
    return m[m["cid_old"] != m["cid_new"]].groupby("cid_old")["fini"].min()


def saldo_final(saldo: pd.DataFrame) -> pd.DataFrame:
    s = saldo.assign(cid=llave(saldo["credito_id"]), f_saldo=fecha(saldo["fecha_transaccion"]),
                     saldo_bd=numero(saldo["saldo"]))
    return s.sort_values("f_saldo").groupby("cid").tail(1).set_index("cid")[["f_saldo", "saldo_bd"]]


def serie_dpd(due_d, due_a, pay_d, pay_a, inicio, fin, tol):
    """DPD diario FIFO entre inicio y fin (datetime64[D])."""
    if fin < inicio or len(due_d) == 0:
        return np.array([], "datetime64[D]"), np.array([], int)
    dias = np.arange(inicio, fin + np.timedelta64(1, "D"), dtype="datetime64[D]")
    cum_due = np.cumsum(due_a)
    if len(pay_d):
        idx = np.searchsorted(pay_d, dias, side="right") - 1
        pagado = np.where(idx >= 0, np.cumsum(pay_a)[np.clip(idx, 0, None)], 0.0)
    else:
        pagado = np.zeros(len(dias))
    j = np.searchsorted(cum_due, pagado + tol, side="right")
    hay = j < len(due_d)
    vieja = np.where(hay, due_d[np.clip(j, 0, len(due_d) - 1)], dias)
    return dias, np.clip(np.where(hay, (dias - vieja).astype(int), 0), 0, None)


def reconstruir(base, plan, pagos, refi, saldo, fecha_corte, tol_rel=P["TOL_REL"], guardar_series=False):
    """Devuelve (tabla por crédito, dict cid -> (días, dpd, fin_obs_A)) si guardar_series."""
    fc = np.datetime64(pd.Timestamp(fecha_corte).date(), "D")
    gp, gq = dict(tuple(plan.groupby("cid"))), dict(tuple(pagos.groupby("cid")))
    filas, series = [], {}
    for r in base.itertuples(index=False):
        p = gp.get(r.cid)
        if p is None:
            continue
        due_d, due_a = p["fecha"].values.astype("datetime64[D]"), p["valorcuota"].values.astype(float)
        q = gq.get(r.cid)
        pay_d = q["fecha"].values.astype("datetime64[D]") if q is not None else np.array([], "datetime64[D]")
        pay_a = q["valor"].values.astype(float) if q is not None else np.array([])
        cuota = float(np.median(due_a[due_a > 0])) if (due_a > 0).any() else 0.0
        tol = max(P["TOL_ABS"], tol_rel * cuota)
        inicio = np.datetime64(pd.Timestamp(r.t_ref).date(), "D")
        ult_pago = pay_d.max() if len(pay_d) else None
        t_refi = refi.get(r.cid)
        sal = saldo["saldo_bd"].get(r.cid, np.nan)
        if r.estado == "ACTIVO":
            cierre, fin_a = "ACTIVO", fc
        elif t_refi is not None and pd.notna(t_refi):
            cierre, fin_a = "REFINANCIACION", min(np.datetime64(pd.Timestamp(t_refi).date(), "D"), fc)
        elif ult_pago is None:
            cierre, fin_a = "SIN_PAGOS", fc
        elif pd.notna(sal) and sal > P["SALDO_CUOTAS"] * max(cuota, 1):
            cierre, fin_a = "CON_SALDO_PENDIENTE", ult_pago
        elif (due_d.max() - ult_pago).astype(int) <= P["PREPAGO_DIAS"]:
            cierre, fin_a = "A_TERMINO", ult_pago
        elif pay_a[-1] >= P["PREPAGO_CUOTAS"] * max(cuota, 1) or pay_a.sum() >= P["PREPAGO_RATIO"] * due_a.sum():
            cierre, fin_a = "PREPAGO", ult_pago
        else:
            cierre, fin_a = "CIERRE_ANTICIPADO_SIN_EXPLICACION", ult_pago
        fin_b = fc if cierre in ("CON_SALDO_PENDIENTE", "SIN_PAGOS", "CIERRE_ANTICIPADO_SIN_EXPLICACION") else fin_a
        dias, dpd = serie_dpd(due_d, due_a, pay_d, pay_a, inicio, fin_b, tol)
        en_a = dias <= fin_a
        dpd_a = dpd[en_a]
        f = {"cid": r.cid, "cierre": cierre, "t_ref": pd.Timestamp(r.t_ref),
             "fin_obs_A": pd.Timestamp(str(fin_a)), "fin_obs_B": pd.Timestamp(str(fin_b)),
             "n_cuotas_plan": len(due_d), "n_pagos": len(pay_d), "cuota_tipica": cuota, "saldo_bd": sal,
             "ratio_pagado_plan": pay_a.sum() / due_a.sum() if due_a.sum() > 0 else np.nan,
             "max_dpd_A": int(dpd_a.max()) if len(dpd_a) else 0,
             "max_dpd_B": int(dpd.max()) if len(dpd) else 0,
             "dpd_fin_A": int(dpd_a[-1]) if len(dpd_a) else 0,
             "dias_obs_A": int((fin_a - inicio).astype(int))}
        for T in P["UMBRALES"]:
            hit = np.nonzero(dpd_a >= T)[0]
            f[f"dias_hasta_{T}"] = int((dias[hit[0]] - inicio).astype(int)) if len(hit) else np.nan
            hitb = np.nonzero(dpd >= T)[0]
            f[f"dias_hasta_{T}_B"] = int((dias[hitb[0]] - inicio).astype(int)) if len(hitb) else np.nan
        for W in P["VENTANAS"]:
            w_fin = np.datetime64((pd.Timestamp(r.t_ref) + pd.DateOffset(months=W)).date(), "D")
            f[f"madura_{W}m"] = bool(w_fin <= fc or (cierre != "ACTIVO" and fin_a <= w_fin))
            sel = dias <= min(w_fin, fin_a)
            f[f"max_dpd_{W}m"] = int(dpd[sel].max()) if sel.any() else 0
            selb = dias <= w_fin
            f[f"max_dpd_{W}m_B"] = int(dpd[selb].max()) if selb.any() else 0
            f[f"dias_obs_{W}m"] = int((min(w_fin, fin_a) - inicio).astype(int))
        if cierre == "REFINANCIACION":
            tr = np.datetime64(pd.Timestamp(t_refi).date(), "D")
            f["dpd_al_refinanciar"] = int(dpd[dias <= tr][-1]) if (dias <= tr).any() else 0
        filas.append(f)
        if guardar_series:
            series[r.cid] = (dias, dpd, fin_a)
    return pd.DataFrame(filas), series


def max_dpd_hasta(series: dict, cid, corte: pd.Timestamp) -> float:
    """Peor DPD observado de un crédito hasta una fecha (sin pasar de su fin de observación A)."""
    if cid not in series:
        return np.nan
    dias, dpd, fin_a = series[cid]
    lim = min(np.datetime64(pd.Timestamp(corte).date(), "D"), fin_a)
    sel = dias <= lim
    return float(dpd[sel].max()) if sel.any() else np.nan
