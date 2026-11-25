"""Carga única de insumos de modelado: población primaria, Home Credit y poblaciones auxiliares."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, diseno, io_datos, modelos

N_HC = 40_000


def cargar(etiqueta: str = "v1.1", objetivo: str = config.EVENTO_PRIMARIO, indeterminados: str = "excluir",
           excluir_cohortes=tuple(config.COHORTES_EXCLUIR), filtro=None, ds=None):
    """Devuelve (D, ctx, ds): población de análisis, contexto de modelos y dataset completo.

    `ds` permite pasar un dataset con etiquetas alternativas (p. ej. otra ventana de la regla D4).
    """
    if ds is None:
        ds = io_datos.leer_parquet(config.PRIVADO / "dataset_analitico_v2.parquet")
    D = diseno.poblacion(ds, objetivo, etiqueta, indeterminados, excluir_cohortes)
    if filtro is not None:
        D = D[filtro(D)].reset_index(drop=True)
    hc = io_datos.leer_parquet(config.HOME_CREDIT_MAPEADO, ["edad_t0", "plazo_meses", "n_creditos_previos",
                                                            "antiguedad_cliente_meses", "peor_mora_previa", "y"])
    X_hc = diseno.construir_X_home_credit(hc)
    beta = modelos.beta_home_credit(X_hc, hc["y"].to_numpy())
    idx = np.random.default_rng(config.SEMILLA).choice(len(hc), N_HC, replace=False)
    lib = ds[(ds["producto"] == "libranza") & ~ds["anio_cohorte"].isin(list(excluir_cohortes))]
    superv = lib[lib["tiempo_90"].notna()].reset_index(drop=True)
    aux = {o: diseno.poblacion(ds, o, etiqueta, "excluir", excluir_cohortes) for o in ("y_60_12m", "y_30_6m")}
    ctx = modelos.Contexto(grupos_primarios=set(D["grupo_cliente"]), beta_hc=beta,
                           X_hc=X_hc.iloc[idx].reset_index(drop=True), y_hc=hc["y"].to_numpy()[idx],
                           supervivencia=superv, auxiliares=aux)
    return D, ctx, ds
