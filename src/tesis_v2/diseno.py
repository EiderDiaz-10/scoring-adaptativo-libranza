"""Diseño de la Fase 3: población, predictores, particiones agrupadas y transformaciones sin fuga.

Todo lo que tiene estado (medianas, cuantiles, WoE, estandarización) se ajusta con el entrenamiento
del pliegue; aquí solo hay transformaciones deterministas fila a fila (logaritmos, indicadores).
Los detalles y su justificación están en 00_protocolo/enmienda_v1.1.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import StratifiedGroupKFold

from . import config

NUCLEO = ["log_monto", "log_plazo", "edad_t0", "tiene_historia", "log_n_previos", "meses_cliente",
          "log_peor_mora_previa", "previo_adverso", "previo_favorable", "n_activos_t0", "log_emp_previos"]
SIGNO_ESPERADO = {"log_monto": 0, "log_plazo": 1, "edad_t0": -1, "tiene_historia": -1, "log_n_previos": -1,
                  "meses_cliente": -1, "log_peor_mora_previa": 1, "previo_adverso": 1, "previo_favorable": -1,
                  "n_activos_t0": 1, "log_emp_previos": -1}
# Variables con definición equivalente en Home Credit (las monetarias no: otra moneda)
COMPARTIDAS = ["edad_t0", "log_plazo", "tiene_historia", "log_n_previos", "meses_cliente", "log_peor_mora_previa"]
# Variables crudas del scorecard M1 (NaN = "sin historia", que recibe su propio intervalo)
SCORECARD = ["monto", "plazo_meses", "edad_t0", "peor_mora_previa", "meses_desde_primer_credito",
             "emp_creditos_previos", "cierre_grupo"]

ADVERSOS, FAVORABLES = ["con_saldo", "refinanciacion"], ["a_termino", "prepago"]


def poblacion(ds: pd.DataFrame, objetivo: str = config.EVENTO_PRIMARIO, etiqueta: str = "v1.1",
              indeterminados: str = "excluir", excluir_cohortes=tuple(config.COHORTES_EXCLUIR),
              producto: str = "libranza") -> pd.DataFrame:
    """Población de análisis para un objetivo.

    etiqueta: "v1.1" (principal; 131 y 250 son incumplimientos confirmados por la operación) u "original" (Fase 1).
    indeterminados: "excluir" (principal), "no_evento" o "evento" (cotas).
    """
    d = ds[(ds["producto"] == producto) & ~ds["anio_cohorte"].isin(list(excluir_cohortes))].copy()
    madura = d["madura_6m"] if objetivo == "y_30_6m" else d["madura_12m"]
    indet = d["cierre_v2"].eq("INDETERMINADO")
    if etiqueta == "v1.1":
        indet &= ~d["cid"].isin(config.CREDITOS_VERIFICAR)
    elif etiqueta != "original":
        raise ValueError(etiqueta)
    if indeterminados == "excluir":
        d = d[madura & ~indet]
    else:
        d = d[madura].copy()
        d.loc[indet.reindex(d.index), objetivo] = 1.0 if indeterminados == "evento" else 0.0
    d = d[d[objetivo].notna()].copy()
    d["y"] = d[objetivo].astype(int)
    return d.reset_index(drop=True)


def construir_X(d: pd.DataFrame) -> pd.DataFrame:
    """Predictores del núcleo (transformaciones deterministas, sin estado)."""
    n_prev = d["n_creditos_previos"].astype(float)
    hist = n_prev > 0
    cierre = d["cierre_previo"].astype(str)
    X = pd.DataFrame({
        "log_monto": np.log(d["monto"].astype(float).clip(lower=1e5)),
        "log_plazo": np.log(d["plazo_meses"].astype(float).clip(lower=1)),
        "edad_t0": d["edad_t0"].astype(float),
        "tiene_historia": hist.astype(float),
        "log_n_previos": np.log1p(n_prev),
        "meses_cliente": d["meses_desde_primer_credito"].astype(float).where(hist, 0.0),
        "log_peor_mora_previa": np.log1p(d["peor_mora_previa"].astype(float).clip(lower=0)).where(hist, 0.0),
        "previo_adverso": cierre.isin(ADVERSOS).astype(float),
        "previo_favorable": cierre.isin(FAVORABLES).astype(float),
        "n_activos_t0": d["n_activos_t0"].astype(float),
        "log_emp_previos": np.log1p(d["emp_creditos_previos"].astype(float).fillna(0)),
    }, index=d.index)
    return X[NUCLEO]


def construir_scorecard(d: pd.DataFrame) -> pd.DataFrame:
    """Variables crudas del scorecard M1."""
    S = d[["monto", "plazo_meses", "edad_t0", "peor_mora_previa", "meses_desde_primer_credito",
           "emp_creditos_previos"]].astype(float).copy()
    c = d["cierre_previo"].astype(str)
    S["cierre_grupo"] = np.select([c.eq("sin_previo"), c.isin(ADVERSOS), c.isin(FAVORABLES)],
                                  ["sin_previo", "adverso", "favorable"], "otro_o_activo")
    return S[SCORECARD]


def construir_X_home_credit(h: pd.DataFrame) -> pd.DataFrame:
    """Variables compartidas construidas en Home Credit con la misma lógica que en FINTECH."""
    n_prev = h["n_creditos_previos"].astype(float)
    hist = n_prev > 0
    meses = h["antiguedad_cliente_meses"].astype(float)
    mora = h["peor_mora_previa"].astype(float).clip(lower=0)
    X = pd.DataFrame({
        "edad_t0": h["edad_t0"].astype(float),
        "log_plazo": np.log(h["plazo_meses"].astype(float).clip(lower=1)),
        "tiene_historia": hist.astype(float),
        "log_n_previos": np.log1p(n_prev),
        "meses_cliente": meses.fillna(meses[hist].median()).where(hist, 0.0),
        "log_peor_mora_previa": np.log1p(mora.fillna(mora[hist].median())).where(hist, 0.0),
    }, index=h.index)
    return X[COMPARTIDAS]


def particiones(grupos, y, n_rep: int = 20, k: int = 5, semilla: int = config.SEMILLA) -> np.ndarray:
    """Matriz (n_rep × n) con el pliegue de prueba de cada crédito en cada repetición."""
    grupos, y = np.asarray(grupos), np.asarray(y)
    F = np.full((n_rep, len(y)), -1, dtype=int)
    for r in range(n_rep):
        cv = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=semilla + r)
        for f, (_, te) in enumerate(cv.split(np.zeros(len(y)), y, grupos)):
            F[r, te] = f
    assert (F >= 0).all()
    return F


def pliegues_internos(grupos, y, k: int = 3, semilla: int = config.SEMILLA):
    cv = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=semilla)
    return list(cv.split(np.zeros(len(y)), np.asarray(y), np.asarray(grupos)))


class WoE(BaseEstimator, TransformerMixin):
    """WoE por intervalos de cuantiles del entrenamiento; NaN y categorías tienen su propio intervalo."""

    def __init__(self, n_bins: int = 4, suavizado: float = 0.5, categoricas=("cierre_grupo",)):
        self.n_bins, self.suavizado, self.categoricas = n_bins, suavizado, categoricas

    def _bin(self, col, x):
        if col in self.categoricas:
            return x.astype(str)
        cortes = self.cortes_[col]
        b = pd.Series(np.searchsorted(cortes, x.to_numpy(float), side="right").astype(str), index=x.index)
        return b.where(x.notna(), "faltante")

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        self.cortes_, self.woe_ = {}, {}
        for col in X.columns:
            if col not in self.categoricas:
                v = X[col].dropna().to_numpy(float)
                q = np.unique(np.quantile(v, np.linspace(0, 1, self.n_bins + 1)[1:-1])) if len(v) else np.array([])
                self.cortes_[col] = q
            b = self._bin(col, X[col])
            t = pd.crosstab(b, y).reindex(columns=[0, 1], fill_value=0)
            dist_b = (t[1] + self.suavizado) / (t[1].sum() + self.suavizado * len(t))
            dist_g = (t[0] + self.suavizado) / (t[0].sum() + self.suavizado * len(t))
            self.woe_[col] = np.log(dist_b / dist_g).to_dict()
        return self

    def transform(self, X: pd.DataFrame):
        return np.column_stack([self._bin(c, X[c]).map(self.woe_[c]).fillna(0.0).to_numpy(float) for c in X.columns])


def resumen_particiones(F: np.ndarray, y, grupos) -> pd.DataFrame:
    y, grupos = np.asarray(y), np.asarray(grupos)
    filas = []
    for r in range(F.shape[0]):
        for f in np.unique(F[r]):
            m = F[r] == f
            filas.append({"repeticion": r, "pliegue": f, "creditos": int(m.sum()), "eventos": int(y[m].sum()),
                          "clientes": len(np.unique(grupos[m]))})
    return pd.DataFrame(filas)
