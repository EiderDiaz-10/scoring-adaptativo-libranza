"""Métricas de probabilidad, discriminación y calibración, con bootstrap por cliente (protocolo v1.1, sección 4).

Las predicciones llegan como matriz P (repeticiones × créditos) de la validación cruzada repetida.
La estimación puntual es la media entre repeticiones de la métrica de cada repetición; el *bootstrap*
remuestrea clientes y repite ese mismo cálculo, de modo que el IC incorpora la incertidumbre muestral.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score
from statsmodels.nonparametric.smoothers_lowess import lowess

from . import config

EPS = 1e-6
RAPIDAS = ["log_loss", "brier", "brier_escalado", "auc", "intercepto_cal", "pendiente_cal"]


def _logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _rapidas(P: np.ndarray, y: np.ndarray) -> dict:
    """Métricas vectorizadas por columna; P es (n × R)."""
    with np.errstate(all="ignore"):
        r = _rapidas_sin_avisos(P, y)
    # Con una predicción constante en la columna (tasa base) la pendiente no está definida.
    constante = np.ptp(P, axis=0) < 1e-12
    r["pendiente_cal"] = np.where(constante, np.nan, r["pendiente_cal"])
    return r


def _rapidas_sin_avisos(P: np.ndarray, y: np.ndarray) -> dict:
    Pc = np.clip(P, EPS, 1 - EPS)
    Y = y[:, None]
    ll = -np.mean(Y * np.log(Pc) + (1 - Y) * np.log(1 - Pc), axis=0)
    br = np.mean((P - Y) ** 2, axis=0)
    prev = y.mean()
    br0 = prev * (1 - prev)
    n1, n0 = y.sum(), len(y) - y.sum()
    if n1 == 0 or n0 == 0:
        auc = np.full(P.shape[1], np.nan)
    else:
        R = rankdata(P, axis=0)
        auc = (R[y == 1].sum(axis=0) - n1 * (n1 + 1) / 2) / (n1 * n0)
    L = _logit(P)
    # pendiente: logística de y sobre [1, logit p] (Newton vectorizado)
    a, b = np.zeros(P.shape[1]), np.ones(P.shape[1])
    for _ in range(25):
        z = a + b * L
        q = 1 / (1 + np.exp(-z))
        w = q * (1 - q)
        g0, g1 = np.sum(Y - q, axis=0), np.sum((Y - q) * L, axis=0)
        h00, h01, h11 = np.sum(w, axis=0), np.sum(w * L, axis=0), np.sum(w * L * L, axis=0)
        det = h00 * h11 - h01 ** 2
        da, db = (h11 * g0 - h01 * g1) / det, (h00 * g1 - h01 * g0) / det
        a, b = a + da, b + db
        if np.nanmax(np.abs(np.r_[da, db])) < 1e-8:
            break
    # intercepto de calibración (calibración en grande): logística con offset logit p
    c = np.zeros(P.shape[1])
    for _ in range(25):
        q = 1 / (1 + np.exp(-(c + L)))
        dc = np.sum(Y - q, axis=0) / np.sum(q * (1 - q), axis=0)
        c += dc
        if np.nanmax(np.abs(dc)) < 1e-10:
            break
    return {"log_loss": ll, "brier": br, "brier_escalado": 1 - br / br0, "auc": auc,
            "intercepto_cal": c, "pendiente_cal": b}


def puntuales(P: np.ndarray, y) -> dict:
    """Media entre repeticiones de cada métrica (incluye las lentas)."""
    y = np.asarray(y, float)
    P = np.atleast_2d(P)
    r = {k: float(np.mean(v)) for k, v in _rapidas(P.T, y).items()}
    r["pr_auc"] = float(np.mean([average_precision_score(y, p) for p in P]))
    r["ks"] = float(np.mean([ks(y, p) for p in P]))
    ici = [calibracion_suave(y, p) for p in P]
    r["ici"], r["e50"], r["e90"] = (float(np.mean([c[i] for c in ici])) for i in range(3))
    r["pd_media"], r["tasa_observada"] = float(P.mean()), float(y.mean())
    return r


def ks(y, p):
    o = np.argsort(p)
    y = np.asarray(y)[o]
    c1, c0 = np.cumsum(y) / y.sum(), np.cumsum(1 - y) / (1 - y).sum()
    return float(np.max(np.abs(c1 - c0)))


def calibracion_suave(y, p, frac=0.75):
    """ICI, E50 y E90 (Austin y Steyerberg, 2019) con lowess."""
    suave = lowess(y, p, frac=frac, it=0, return_sorted=False)
    d = np.abs(suave - p)
    return float(d.mean()), float(np.median(d)), float(np.quantile(d, 0.9))


def indices_bootstrap(grupos, B=2000, semilla=config.SEMILLA):
    """Índices de filas para B réplicas de clientes remuestreados con reemplazo."""
    grupos = np.asarray(grupos)
    unicos, inv = np.unique(grupos, return_inverse=True)
    filas = [np.flatnonzero(inv == g) for g in range(len(unicos))]
    rng = np.random.default_rng(semilla)
    for _ in range(B):
        sel = rng.integers(0, len(unicos), len(unicos))
        yield np.concatenate([filas[g] for g in sel])


def bootstrap(Ps: dict, y, grupos, B=2000, semilla=config.SEMILLA) -> dict:
    """Distribución bootstrap (B × métricas) de cada modelo, con las mismas réplicas para todos."""
    y = np.asarray(y, float)
    salida = {k: {m: np.empty(B) for m in RAPIDAS} for k in Ps}
    for b, idx in enumerate(indices_bootstrap(grupos, B, semilla)):
        yb = y[idx]
        for k, P in Ps.items():
            r = _rapidas(np.atleast_2d(P)[:, idx].T, yb)
            for m in RAPIDAS:
                salida[k][m][b] = np.nanmean(r[m])
    return {k: pd.DataFrame(v) for k, v in salida.items()}


def tabla_resultados(Ps: dict, y, boot: dict, nombres: dict | None = None) -> pd.DataFrame:
    filas = []
    for k, P in Ps.items():
        pt = puntuales(P, y)
        fila = {"modelo": k, "nombre": (nombres or {}).get(k, k)}
        for m, v in pt.items():
            fila[m] = v
            if m in RAPIDAS:
                lo, hi = np.nanpercentile(boot[k][m], [2.5, 97.5])
                fila[f"{m}_ic"] = f"{lo:.3f}–{hi:.3f}"
        fila["auc_de_repeticiones"] = float(np.std(_rapidas(np.atleast_2d(P).T, np.asarray(y, float))["auc"]))
        filas.append(fila)
    return pd.DataFrame(filas)


def comparacion_pareada(boot: dict, puntual: pd.DataFrame, a: str, b: str, metrica="log_loss") -> dict:
    """Δ = métrica(a) − métrica(b) con IC bootstrap pareado y p-valor bilateral."""
    d = boot[a][metrica].to_numpy() - boot[b][metrica].to_numpy()
    d = d[~np.isnan(d)]
    est = float(puntual.set_index("modelo").loc[a, metrica] - puntual.set_index("modelo").loc[b, metrica])
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = float(min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean())))
    return {"modelo": a, "frente_a": b, "metrica": metrica, "delta": est, "ic_inf": lo, "ic_sup": hi, "p_bootstrap": p}


def holm(p: pd.Series) -> pd.Series:
    orden = p.sort_values()
    m = len(orden)
    ajust = np.maximum.accumulate([(m - i) * v for i, v in enumerate(orden.to_numpy())])
    return pd.Series(np.minimum(1, ajust), index=orden.index).reindex(p.index)


def beneficio_neto(y, p, umbrales):
    y, p = np.asarray(y), np.asarray(p)
    n = len(y)
    filas = []
    for t in umbrales:
        marca = p >= t
        tp, fp = np.sum(marca & (y == 1)), np.sum(marca & (y == 0))
        filas.append({"umbral": t, "modelo": tp / n - fp / n * t / (1 - t),
                      "marcar_todos": y.mean() - (1 - y.mean()) * t / (1 - t)})
    return pd.DataFrame(filas)
