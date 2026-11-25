"""Etiquetas del evento, indeterminados y elegibilidad (reglas D3 a D6 de la v1, evento primario 90+)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .io_datos import fecha, llave, numero


def etiquetar(obj: pd.DataFrame, base: pd.DataFrame, cred: pd.DataFrame, saldo: pd.DataFrame,
              ventana_refi: tuple[int, int] = config.VENTANA_REFI) -> pd.DataFrame:
    """Aplica D3-D6 y construye y_90_12m (primario), y_60_12m, y_30_6m y el objetivo de supervivencia.

    D3  Refinanciación enlazada = cierre sin evento; la mora previa a la refinanciación sí cuenta.
    D4  Refinanciación no enlazada: cierre con saldo (o anticipado sin explicación) cuyo cliente recibe
        otro crédito entre ventana_refi[0] y ventana_refi[1] días del cierre por un monto >= saldo.
    D5  Cierre con saldo restante: con crédito posterior del mismo cliente -> recurrente (sin evento
        adicional); sin crédito posterior -> INDETERMINADO (se excluye y se reportan cotas).
    D6  Elegible = ventana de 12 meses madura, no indeterminado, cohorte distinta de 2021.
    """
    t = obj.merge(base[["cid", "cli", "anio_cohorte", "estado", "cnfrecaudo", "producto", "t0"]], on="cid")
    t["f_cierre"] = np.where(t["cierre"] == "CON_SALDO_PENDIENTE",
                             t["cid"].map(saldo["f_saldo"]).fillna(t["fin_obs_A"]), t["fin_obs_A"])
    t["f_cierre"] = pd.to_datetime(t["f_cierre"])

    c = cred[~cred["estado"].isin(["ANULADO", "PENDIENTE_DESEMBOLSO"])]
    c = pd.DataFrame({"cid2": llave(c["id"]), "cli": llave(c["cliente_id"]),
                      "ini2": fecha(c["fechainicialcredito"]), "vt2": numero(c["valortotal"])})
    o = t[["cid", "cli", "f_cierre", "saldo_bd"]].merge(c, on="cli")
    o = o[o["cid2"] != o["cid"]]
    o["dif"] = (o["ini2"] - o["f_cierre"]).dt.days
    a, b = ventana_refi
    o["refi_ne"] = o["dif"].between(a, b) & (o["vt2"] >= o["saldo_bd"].fillna(0))
    g = o.groupby("cid").agg(refi_no_enlazada=("refi_ne", "any"),
                             credito_posterior=("dif", lambda d: bool((d > b).any())))
    t = t.merge(g, on="cid", how="left")
    t[["refi_no_enlazada", "credito_posterior"]] = t[["refi_no_enlazada", "credito_posterior"]].fillna(False).astype(bool)

    t["cierre_v2"] = t["cierre"]
    recl = t["cierre"].isin(["CON_SALDO_PENDIENTE", "CIERRE_ANTICIPADO_SIN_EXPLICACION"])
    t.loc[recl & t["refi_no_enlazada"], "cierre_v2"] = "REFINANCIACION_NO_ENLAZADA"
    resto = t["cierre_v2"] == "CON_SALDO_PENDIENTE"
    t.loc[resto & t["credito_posterior"], "cierre_v2"] = "CON_SALDO_CLIENTE_RECURRENTE"
    t.loc[resto & ~t["credito_posterior"], "cierre_v2"] = "INDETERMINADO"

    t["y_90_12m"] = np.where(t["madura_12m"], (t["max_dpd_12m"] >= 90).astype(float), np.nan)
    t["y_60_12m"] = np.where(t["madura_12m"], (t["max_dpd_12m"] >= 60).astype(float), np.nan)
    t["y_30_6m"] = np.where(t["madura_6m"], (t["max_dpd_6m"] >= 30).astype(float), np.nan)
    t["y_90_12m_B"] = np.where(t["madura_12m"], (t["max_dpd_12m_B"] >= 90).astype(float), np.nan)

    t["motivo_exclusion"] = np.select(
        [~t["madura_12m"], t["cierre_v2"] == "INDETERMINADO", t["anio_cohorte"].isin(config.COHORTES_EXCLUIR)],
        ["VENTANA_INMADURA", "INDETERMINADO", "COHORTE_2021"], default="")
    t["elegible"] = t["motivo_exclusion"] == ""
    t["conjunto_temporal"] = np.where(t["anio_cohorte"] >= config.ANIO_BACKTEST, "2025+", "<2025")

    # Supervivencia: tiempo (días) desde el desembolso hasta el primer día con DPD >= 90.
    # Se censura en el fin de observación A (corte, refinanciación o último pago).
    t["evento_90"] = t["dias_hasta_90"].notna().astype(int)
    t["tiempo_90"] = np.where(t["evento_90"] == 1, t["dias_hasta_90"], t["dias_obs_A"]).astype(float)
    return t


def cargar_y_reconstruir(tol_rel: float | None = None, ventana_refi=config.VENTANA_REFI, guardar_series=False):
    """Lee el export, reconstruye la mora y etiqueta. Devuelve un dict con todas las piezas."""
    from . import mora
    from .io_datos import leer_tabla
    tablas = {n: leer_tabla(n) for n in ["credito", "solicitud", "desembolso", "tipocredito",
                                          "proyeccionpagos", "transaccionpago", "saldo"]}
    base = mora.preparar_base(tablas["credito"], tablas["solicitud"], tablas["desembolso"], tablas["tipocredito"])
    plan = mora.plan_vigente(tablas["proyeccionpagos"])
    pagos, n_dup = mora.pagos_validos(tablas["transaccionpago"])
    refi = mora.enlaces_refinanciacion(tablas["solicitud"], tablas["credito"])
    saldo = mora.saldo_final(tablas["saldo"])
    corte = pagos["fecha"].max()
    obj, series = mora.reconstruir(base, plan, pagos, refi, saldo, corte,
                                   tol_rel=config.PARAMS_MORA["TOL_REL"] if tol_rel is None else tol_rel,
                                   guardar_series=guardar_series)
    t = etiquetar(obj, base, tablas["credito"], saldo, ventana_refi)
    return {"tablas": tablas, "base": base, "plan": plan, "pagos": pagos, "n_pagos_dup": n_dup,
            "refi": refi, "saldo": saldo, "corte": corte, "objetivo": t, "series": series}


def cotas_indeterminados(t: pd.DataFrame, evento: str = "y_90_12m", filtro=None) -> pd.DataFrame:
    """Tasa del evento bajo tres tratamientos de los indeterminados maduros."""
    base = t[t["madura_12m"] & ~t["anio_cohorte"].isin(config.COHORTES_EXCLUIR)]
    if filtro is not None:
        base = base[filtro(base)]
    ind = base[base["cierre_v2"] == "INDETERMINADO"]
    ok = base[base["cierre_v2"] != "INDETERMINADO"]
    ev_ok = int(ok[evento].sum())
    filas = [
        ("Indeterminados excluidos (principal)", len(ok), ev_ok),
        ("Indeterminados = no evento (cota inferior)", len(base), ev_ok),
        ("Indeterminados según su mora observada", len(base), ev_ok + int(ind[evento].sum())),
        ("Indeterminados = evento (cota superior)", len(base), ev_ok + len(ind)),
    ]
    df = pd.DataFrame(filas, columns=["escenario", "creditos", "eventos"])
    df["tasa_%"] = (100 * df["eventos"] / df["creditos"]).round(2)
    return df
