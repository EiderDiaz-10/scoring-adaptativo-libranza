"""Funciones estadísticas compartidas: intervalos, WoE/IV, AUC, PSI, Kaplan-Meier y tamaño muestral."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

from .config import SEMILLA


# ---------------------------------------------------------------- proporciones
def wilson(eventos, n, alpha=0.05):
    """IC de Wilson para una proporción (se comporta bien con pocos eventos)."""
    eventos, n = np.asarray(eventos, float), np.asarray(n, float)
    z = stats.norm.ppf(1 - alpha / 2)
    p = np.divide(eventos, n, out=np.zeros_like(eventos), where=n > 0)
    den = 1 + z ** 2 / n
    centro = (p + z ** 2 / (2 * n)) / den
    medio = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return np.clip(centro - medio, 0, 1), np.clip(centro + medio, 0, 1)


def tabla_tasa(df: pd.DataFrame, por, evento: str) -> pd.DataFrame:
    g = df.groupby(por, observed=True)[evento].agg(creditos="count", eventos="sum").reset_index()
    g["eventos"] = g["eventos"].astype(int)
    g["tasa_%"] = 100 * g["eventos"] / g["creditos"]
    lo, hi = wilson(g["eventos"], g["creditos"])
    g["ic95_inf_%"], g["ic95_sup_%"] = 100 * lo, 100 * hi
    return g.round(2)


# ---------------------------------------------------------------- WoE / IV
def discretizar(x: pd.Series, n_bins: int = 5, cortes=None):
    """Cortes por cuantiles (calculados en los datos de referencia) y una categoría para faltantes."""
    if cortes is None:
        q = np.unique(np.nanquantile(x.dropna(), np.linspace(0, 1, n_bins + 1)))
        cortes = np.concatenate([[-np.inf], q[1:-1], [np.inf]]) if len(q) > 2 else np.array([-np.inf, np.inf])
    b = pd.cut(x, cortes, include_lowest=True, duplicates="drop").astype("string")
    return b.fillna("Faltante"), cortes


def woe_iv(categoria: pd.Series, y: pd.Series, suavizado: float = 0.5) -> tuple[pd.DataFrame, float]:
    """WoE = ln(%no_eventos / %eventos), con suavizado de Laplace para las celdas sin eventos."""
    t = pd.crosstab(categoria, y).reindex(columns=[0, 1], fill_value=0)
    t.columns = ["no_eventos", "eventos"]
    ne = (t["no_eventos"] + suavizado) / (t["no_eventos"].sum() + suavizado * len(t))
    ev = (t["eventos"] + suavizado) / (t["eventos"].sum() + suavizado * len(t))
    t["creditos"] = t["no_eventos"] + t["eventos"]
    t["tasa_%"] = 100 * t["eventos"] / t["creditos"]
    t["woe"] = np.log(ne / ev)
    t["iv_parcial"] = (ne - ev) * t["woe"]
    return t, float(t["iv_parcial"].sum())


def bootstrap_por_cliente(df: pd.DataFrame, grupo: str, estadistico, B: int = 1000, semilla: int = SEMILLA):
    """Remuestrea clientes completos (no créditos) para respetar la dependencia dentro de cada cliente."""
    rng = np.random.default_rng(semilla)
    idx_por_grupo = df.groupby(grupo).indices
    grupos = np.array(list(idx_por_grupo))
    valores = []
    for _ in range(B):
        g = rng.choice(grupos, size=len(grupos), replace=True)
        idx = np.concatenate([idx_por_grupo[k] for k in g])
        try:
            valores.append(estadistico(df.iloc[idx].reset_index(drop=True)))
        except ValueError:
            continue
    return np.array(valores, float)


def auc_orientado(x: pd.Series, y: pd.Series) -> float:
    """AUC de una sola variable (sin faltantes). Un valor < 0,5 indica una relación inversa."""
    ok = x.notna()
    if y[ok].nunique() < 2:
        return np.nan
    return roc_auc_score(y[ok], x[ok])


# ---------------------------------------------------------------- estabilidad
def psi(referencia: pd.Series, actual: pd.Series, n_bins: int = 10, eps: float = 1e-4) -> float:
    """Population Stability Index con cortes por cuantiles de la referencia; los faltantes son una categoría."""
    ref, act = referencia, actual
    if pd.api.types.is_numeric_dtype(ref) and ref.nunique() > n_bins:
        q = np.unique(np.nanquantile(ref.dropna(), np.linspace(0, 1, n_bins + 1)))
        cortes = np.concatenate([[-np.inf], q[1:-1], [np.inf]])
        ref = pd.cut(ref, cortes, duplicates="drop").astype("string")
        act = pd.cut(act, cortes, duplicates="drop").astype("string")
    ref, act = ref.astype("string").fillna("NA"), act.astype("string").fillna("NA")
    cats = sorted(set(ref.dropna()) | set(act.dropna()))
    p = ref.value_counts(normalize=True).reindex(cats, fill_value=0) + eps
    q = act.value_counts(normalize=True).reindex(cats, fill_value=0) + eps
    return float(((q - p) * np.log(q / p)).sum())


# ---------------------------------------------------------------- supervivencia
def kaplan_meier(tiempo, evento, grilla=None, alpha=0.05) -> pd.DataFrame:
    """Kaplan-Meier con IC log(-log) de Greenwood. Devuelve S(t) y la incidencia acumulada 1-S(t)."""
    tiempo, evento = np.asarray(tiempo, float), np.asarray(evento, int)
    orden = np.argsort(tiempo)
    tiempo, evento = tiempo[orden], evento[orden]
    z = stats.norm.ppf(1 - alpha / 2)
    s, var_acum = 1.0, 0.0
    filas = [(0.0, 1.0, 1.0, 1.0, len(tiempo), 0)]
    for tt in np.unique(tiempo[evento == 1]):
        n_riesgo = int((tiempo >= tt).sum())
        d = int(((tiempo == tt) & (evento == 1)).sum())
        s *= 1 - d / n_riesgo
        if n_riesgo > d:
            var_acum += d / (n_riesgo * (n_riesgo - d))
        if 0 < s < 1:
            se = np.sqrt(var_acum) / abs(np.log(s))
            lo, hi = s ** np.exp(z * se), s ** np.exp(-z * se)
        else:
            lo = hi = s
        filas.append((tt, s, lo, hi, n_riesgo, d))
    km = pd.DataFrame(filas, columns=["t", "S", "S_inf", "S_sup", "en_riesgo", "eventos"])
    if grilla is not None:
        grilla = np.asarray(grilla, float)
        idx = np.searchsorted(km["t"].values, grilla, side="right") - 1
        km = km.iloc[idx].reset_index(drop=True).assign(t=grilla)
        km["en_riesgo"] = [int((tiempo >= g).sum()) for g in grilla]
    km["incidencia"], km["inc_inf"], km["inc_sup"] = 1 - km["S"], 1 - km["S_sup"], 1 - km["S_inf"]
    return km


# ---------------------------------------------------------------- potencia y tamaño muestral
def se_auc_hanley(auc: float, n_eventos: int, n_no_eventos: int) -> float:
    """Error estándar del AUC de Hanley y McNeil (1982)."""
    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    v = auc * (1 - auc) + (n_eventos - 1) * (q1 - auc ** 2) + (n_no_eventos - 1) * (q2 - auc ** 2)
    return float(np.sqrt(v / (n_eventos * n_no_eventos)))


def r2cs_desde_auc(auc: float, prevalencia: float, n: int = 400_000, semilla: int = SEMILLA) -> float:
    """R² de Cox-Snell esperado para un AUC y una prevalencia (simulación al estilo de Riley et al. 2021).

    Supone un predictor lineal normal en escala logit; ajusta la media y la desviación para reproducir la
    prevalencia y el AUC, y calcula R²cs = 1 - exp(-2(ll_modelo - ll_nulo)/n).
    """
    from scipy.optimize import brentq
    rng = np.random.default_rng(semilla)
    z = rng.standard_normal(n)
    u = rng.random(n)

    def media_para(sd):
        return brentq(lambda m: np.mean(1 / (1 + np.exp(-(m + sd * z)))) - prevalencia, -30, 10)

    def simular(sd):
        p = 1 / (1 + np.exp(-(media_para(sd) + sd * z)))
        y = u < p
        return roc_auc_score(y, p), p, y

    sd = brentq(lambda s: simular(s)[0] - auc, 0.05, 6, xtol=1e-3)
    _, p, y = simular(sd)
    ll_modelo = np.sum(np.where(y, np.log(p), np.log(1 - p)))
    phi = y.mean()
    ll_nulo = n * (phi * np.log(phi) + (1 - phi) * np.log(1 - phi))
    return float(1 - np.exp(-2 * (ll_modelo - ll_nulo) / n))


def riley_binario(parametros: int, prevalencia: float, r2cs: float, s: float = 0.9, delta: float = 0.05) -> dict:
    """Tamaño mínimo de muestra para un modelo de predicción binario (Riley et al. 2020, criterios 1 a 3)."""
    ln_l0 = prevalencia * np.log(prevalencia) + (1 - prevalencia) * np.log(1 - prevalencia)
    max_r2 = 1 - np.exp(2 * ln_l0)
    n1 = parametros / ((s - 1) * np.log(1 - r2cs / s))
    s2 = r2cs / (r2cs + delta * max_r2)
    n2 = parametros / ((s2 - 1) * np.log(1 - r2cs / s2))
    n3 = (1.96 / 0.05) ** 2 * prevalencia * (1 - prevalencia)
    n = int(np.ceil(max(n1, n2, n3)))
    return {"n_crit1_contraccion": int(np.ceil(n1)), "n_crit2_optimismo": int(np.ceil(n2)),
            "n_crit3_intercepto": int(np.ceil(n3)), "n_minimo": n,
            "eventos_minimos": int(np.ceil(n * prevalencia)), "max_r2cs": round(float(max_r2), 4)}
