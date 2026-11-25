"""Batería cerrada de modelos M0–M7 (protocolo v1.1, sección 3).

Interfaz común: `ajustar(D, ctx)` con las filas de entrenamiento del pliegue (columnas del dataset
analítico más `y`) y `predecir(D)` → probabilidad de incumplimiento. Los hiperparámetros se eligen
dentro de `ajustar` con un pliegue interno agrupado por cliente, nunca con la prueba.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .diseno import (COMPARTIDAS, NUCLEO, SIGNO_ESPERADO, WoE, construir_scorecard, construir_X,
                     pliegues_internos)

warnings.filterwarnings("ignore", category=ConvergenceWarning)
EPS = 1e-6
GRILLA_C = list(np.logspace(-3, 1, 7))


def _ll(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


@dataclass
class Contexto:
    """Insumos fijos que algunos modelos necesitan además del entrenamiento del pliegue."""
    grupos_primarios: set
    beta_hc: pd.Series | None = None              # coeficientes de Home Credit por unidad natural
    X_hc: pd.DataFrame | None = None              # submuestra de Home Credit (variables compartidas)
    y_hc: np.ndarray | None = None
    supervivencia: pd.DataFrame | None = None     # libranza 2022+ con tiempo_90 / evento_90
    auxiliares: dict = field(default_factory=dict)  # objetivo -> población con columna y

    def permitidas(self, extra: pd.DataFrame, D: pd.DataFrame) -> pd.DataFrame:
        """Filas extra sin clientes que estén fuera del entrenamiento (prueba externa o interna)."""
        fuera = self.grupos_primarios - set(D["grupo_cliente"])
        return extra[~extra["grupo_cliente"].isin(fuera)]


def ajustar_con_interno(D, ctx, crear, grilla):
    """Elige la configuración con menor log loss en un 3-fold interno agrupado y reajusta con todo D."""
    if len(grilla) == 1:
        return crear(grilla[0]).ajustar(D, ctx), grilla[0]
    folds = pliegues_internos(D["grupo_cliente"], D["y"])
    mejor, mejor_ll = None, np.inf
    for cfg in grilla:
        p = np.empty(len(D))
        for tr, te in folds:
            p[te] = crear(cfg).ajustar(D.iloc[tr], ctx).predecir(D.iloc[te])
        ll = _ll(D["y"].to_numpy(), p)
        if ll < mejor_ll:
            mejor, mejor_ll = cfg, ll
    return crear(mejor).ajustar(D, ctx), mejor


class Base:
    nombre = ""
    elegido = None

    def ajustar(self, D, ctx):
        raise NotImplementedError

    def predecir(self, D):
        raise NotImplementedError


# ------------------------------------------------------------------ M0: referencias
class M0aTasaBase(Base):
    nombre = "M0a Tasa base"

    def ajustar(self, D, ctx):
        self.p = (D["y"].sum() + 0.5) / (len(D) + 1)
        return self

    def predecir(self, D):
        return np.full(len(D), self.p)


def incumple_politica(D: pd.DataFrame) -> np.ndarray:
    """Proxy de la política vigente con las reglas evaluables en t0 (P01, P15, P16, P20)."""
    edad, monto, plazo = D["edad_t0"].astype(float), D["monto"].astype(float), D["plazo_meses"].astype(float)
    p01 = edad.notna() & ~edad.between(18, 72)
    p15 = ~monto.between(4e5, 4.5e7)
    p16 = ~plazo.round().between(6, 60)
    p20 = (D["n_creditos_previos"] > 0) & (D["peor_mora_previa"].astype(float) >= 30)
    return (p01 | p15 | p16 | p20).to_numpy()


class M0bPolitica(Base):
    nombre = "M0b Regla de políticas"

    def ajustar(self, D, ctx):
        f, y = incumple_politica(D), D["y"].to_numpy()
        self.p = {k: (y[f == k].sum() + 0.5) / ((f == k).sum() + 1) for k in (False, True)}
        return self

    def predecir(self, D):
        f = incumple_politica(D)
        return np.where(f, self.p[True], self.p[False])


# ------------------------------------------------------------------ M1: scorecard WoE
class _Scorecard(Base):
    def __init__(self, n_bins):
        self.n_bins = n_bins

    def ajustar(self, D, ctx):
        self.woe = WoE(self.n_bins)
        Z = self.woe.fit(construir_scorecard(D), D["y"]).transform(construir_scorecard(D))
        self.lr = LogisticRegression(C=1.0, max_iter=2000).fit(Z, D["y"])
        return self

    def predecir(self, D):
        return self.lr.predict_proba(self.woe.transform(construir_scorecard(D)))[:, 1]


class M1Scorecard(Base):
    nombre = "M1 Scorecard WoE"

    def ajustar(self, D, ctx):
        self.m, self.elegido = ajustar_con_interno(D, ctx, _Scorecard, [3, 4, 5])
        return self

    def predecir(self, D):
        return self.m.predecir(D)


# ------------------------------------------------------------------ M2: logística penalizada
def _caracteristicas(D, extra=None):
    X = construir_X(D)
    if extra:
        for nombre, fn in extra.items():
            X[nombre] = fn(D)
    return X


class _Logistica(Base):
    def __init__(self, cfg, extra=None):
        self.C, self.l1 = cfg
        self.extra = extra

    def ajustar(self, D, ctx):
        solver = "lbfgs" if self.l1 == 0 else ("liblinear" if self.l1 == 1 else "saga")
        self.pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                  LogisticRegression(C=self.C, l1_ratio=self.l1, solver=solver, max_iter=5000,
                                                     random_state=config.SEMILLA))
        self.pipe.fit(_caracteristicas(D, self.extra), D["y"])
        return self

    def predecir(self, D):
        return self.pipe.predict_proba(_caracteristicas(D, self.extra))[:, 1]

    def coeficientes(self):
        return pd.Series(self.pipe[-1].coef_[0], index=self.pipe[-1].feature_names_in_
                         if hasattr(self.pipe[-1], "feature_names_in_") else None)


class M2Penalizada(Base):
    nombre = "M2 Logística penalizada"

    def __init__(self, penalizaciones=(0.0, 1.0, 0.25, 0.5, 0.75), extra=None):
        self.grilla = [(C, l1) for l1 in penalizaciones for C in GRILLA_C]
        self.extra = extra

    def ajustar(self, D, ctx):
        self.m, self.elegido = ajustar_con_interno(D, ctx, lambda c: _Logistica(c, self.extra), self.grilla)
        return self

    def predecir(self, D):
        return self.m.predecir(D)

    def coeficientes(self, D):
        cols = list(_caracteristicas(D.iloc[:2], self.extra).columns)
        return pd.Series(self.m.pipe[-1].coef_[0], index=cols)


class M2Firth(Base):
    """Logística con penalización de Firth (prior de Jeffreys): reduce el sesgo con pocos eventos."""
    nombre = "M2F Logística de Firth"

    def ajustar(self, D, ctx):
        self.prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        X = self.prep.fit_transform(construir_X(D))
        X = np.column_stack([np.ones(len(X)), X])
        y = D["y"].to_numpy(float)
        b = np.zeros(X.shape[1])

        def lpen(b):
            p = expit(X @ b)
            W = p * (1 - p)
            sign, logdet = np.linalg.slogdet(X.T @ (X * W[:, None]))
            return np.sum(y * np.log(np.clip(p, EPS, 1)) + (1 - y) * np.log(np.clip(1 - p, EPS, 1))) + 0.5 * logdet

        actual = lpen(b)
        for _ in range(100):
            p = expit(X @ b)
            W = p * (1 - p)
            I = X.T @ (X * W[:, None])
            Iinv = np.linalg.inv(I)
            h = np.einsum("ij,jk,ik->i", X * np.sqrt(W)[:, None], Iinv, X * np.sqrt(W)[:, None])
            U = X.T @ (y - p + h * (0.5 - p))
            paso = Iinv @ U
            for _ in range(30):
                nuevo = lpen(b + paso)
                if nuevo >= actual - 1e-10:
                    break
                paso /= 2
            b, cambio, actual = b + paso, np.abs(paso).max(), nuevo
            if cambio < 1e-7:
                break
        self.b = b
        self.cov = np.linalg.inv(X.T @ (X * (expit(X @ b) * (1 - expit(X @ b)))[:, None]))
        return self

    def predecir(self, D):
        X = self.prep.transform(construir_X(D))
        return expit(self.b[0] + X @ self.b[1:])


# ------------------------------------------------------------------ M3: Home Credit como prior
def map_logistica(X, y, mu, sd, w=None):
    """Máximo a posteriori con β ~ N(mu, sd²) e intercepto plano; devuelve (b0, b, cov de Laplace)."""
    n, k = X.shape
    w = np.ones(n) if w is None else w
    p0 = np.clip(np.average(y, weights=w), 1e-3, 1 - 1e-3)

    def f(th):
        z = th[0] + X @ th[1:]
        r = w * (expit(z) - y)
        val = np.sum(w * (np.logaddexp(0, z) - y * z)) + np.sum((th[1:] - mu) ** 2 / (2 * sd ** 2))
        grad = np.concatenate([[r.sum()], X.T @ r + (th[1:] - mu) / sd ** 2])
        return val, grad

    res = minimize(f, np.concatenate([[logit(p0)], mu]), jac=True, method="L-BFGS-B")
    th = res.x
    pz = expit(th[0] + X @ th[1:])
    Xt = np.column_stack([np.ones(n), X])
    H = Xt.T @ (Xt * (w * pz * (1 - pz))[:, None])
    H[1:, 1:] += np.diag(1 / sd ** 2 * np.ones(k))
    return th[0], th[1:], np.linalg.inv(H)


class _Prior(Base):
    def __init__(self, tau, centro_hc=True):
        self.tau, self.centro_hc = tau, centro_hc

    def ajustar(self, D, ctx):
        self.prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        Xr = construir_X(D)
        X = self.prep.fit_transform(Xr)
        de = self.prep[-1].scale_
        self.mu = np.zeros(len(NUCLEO))
        if self.centro_hc:
            for j, v in enumerate(NUCLEO):
                if v in COMPARTIDAS:
                    self.mu[j] = ctx.beta_hc[v] * de[j]
        self.b0, self.b, self.cov = map_logistica(X, D["y"].to_numpy(float), self.mu, self.tau)
        return self

    def predecir(self, D):
        return expit(self.b0 + self.prep.transform(construir_X(D)) @ self.b)


class M3PriorHomeCredit(Base):
    nombre = "M3 Bayesiana con prior Home Credit"

    def __init__(self, taus=(0.25, 0.5, 1.0, 2.0, 4.0), centro_hc=True):
        self.taus, self.centro_hc = list(taus), centro_hc

    def ajustar(self, D, ctx):
        self.m, self.elegido = ajustar_con_interno(D, ctx, lambda t: _Prior(t, self.centro_hc), self.taus)
        return self

    def predecir(self, D):
        return self.m.predecir(D)


def beta_home_credit(X_hc: pd.DataFrame, y_hc) -> pd.Series:
    """Logística sin penalizar en Home Credit, por unidad natural de cada variable compartida."""
    import statsmodels.api as sm

    res = sm.Logit(np.asarray(y_hc), sm.add_constant(X_hc, has_constant="add")).fit(disp=0, maxiter=200)
    return res.params[X_hc.columns]


# ------------------------------------------------------------------ M4: configuración v1 (apilado)
class M4ApiladoV1(Base):
    nombre = "M4 Apilado v1 (HC 80 %)"

    def __init__(self, fraccion_hc=0.8):
        self.f = fraccion_hc

    def ajustar(self, D, ctx):
        Xi = construir_X(D)
        self.imp = SimpleImputer(strategy="median").fit(Xi)
        Xi = pd.DataFrame(self.imp.transform(Xi), columns=NUCLEO)
        yi = D["y"].to_numpy()
        if self.f > 0:
            Xh = pd.DataFrame({v: (ctx.X_hc[v].to_numpy() if v in COMPARTIDAS else np.full(len(ctx.X_hc), Xi[v].mean()))
                               for v in NUCLEO})
            X = pd.concat([Xi, Xh], ignore_index=True)
            fuente = np.r_[np.zeros(len(Xi)), np.ones(len(Xh))]
            y = np.r_[yi, ctx.y_hc]
            w = np.r_[np.ones(len(Xi)), np.full(len(Xh), self.f * len(Xi) / ((1 - self.f) * len(Xh)))]
        else:
            X, fuente, y, w = Xi, np.zeros(len(Xi)), yi, np.ones(len(Xi))
        self.esc = StandardScaler().fit(Xi)
        Z = np.column_stack([self.esc.transform(X), fuente])
        self.lr = LogisticRegression(C=1.0, max_iter=5000).fit(Z, y, sample_weight=w * len(y) / w.sum())
        return self

    def predecir(self, D):
        Z = self.esc.transform(pd.DataFrame(self.imp.transform(construir_X(D)), columns=NUCLEO))
        return self.lr.predict_proba(np.column_stack([Z, np.zeros(len(Z))]))[:, 1]


# ------------------------------------------------------------------ M5: boosting acotado y monótono
class _Boosting(Base):
    def __init__(self, cfg):
        self.prof, self.arboles, self.tasa = cfg

    def ajustar(self, D, ctx):
        self.m = HistGradientBoostingClassifier(
            max_depth=self.prof, max_leaf_nodes=2 ** self.prof, max_iter=self.arboles, learning_rate=self.tasa,
            min_samples_leaf=20, l2_regularization=1.0, early_stopping=False,
            monotonic_cst=[SIGNO_ESPERADO[v] for v in NUCLEO], random_state=config.SEMILLA)
        self.m.fit(construir_X(D), D["y"])
        return self

    def predecir(self, D):
        return self.m.predict_proba(construir_X(D))[:, 1]


class M5Boosting(Base):
    nombre = "M5 Boosting monótono"
    GRILLA = [(p, a, t) for p in (1, 2) for a in (50, 100, 200) for t in (0.05, 0.1)]

    def ajustar(self, D, ctx):
        self.m, self.elegido = ajustar_con_interno(D, ctx, _Boosting, self.GRILLA)
        return self

    def predecir(self, D):
        return self.m.predecir(D)


# ------------------------------------------------------------------ M6: supervivencia en tiempo discreto
MES = 30.44
TRAMOS = [(4, 6), (7, 9), (10, 12)]


def persona_mes(S: pd.DataFrame, X: np.ndarray):
    """Expande créditos a registros crédito-mes (meses 4 a 12) con su indicador de evento."""
    t = S["tiempo_90"].to_numpy(float)
    e = S["evento_90"].to_numpy(int) * (t <= 12 * MES)
    ultimo = np.minimum(12, np.ceil(t / MES)).astype(int)
    filas, meses, ev = [], [], []
    for i in range(len(S)):
        for m in range(4, ultimo[i] + 1):
            filas.append(i)
            meses.append(m)
            ev.append(int(e[i] and m == ultimo[i]))
    filas, meses = np.array(filas, int), np.array(meses, int)
    return X[filas], meses, np.array(ev, int)


def _tramos(meses):
    # Escalar por 10 equivale a penalizar 100 veces menos el riesgo base que los predictores.
    return np.column_stack([10.0 * ((meses >= a) & (meses <= b)) for a, b in TRAMOS[1:]])


class _Discreto(Base):
    def __init__(self, C):
        self.C = C

    def ajustar(self, D, ctx):
        S = ctx.permitidas(ctx.supervivencia, D)
        self.prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        X = self.prep.fit_transform(construir_X(S))
        Xp, meses, ev = persona_mes(S, X)
        self.lr = LogisticRegression(C=self.C, max_iter=5000).fit(np.column_stack([Xp, _tramos(meses)]), ev)
        return self

    def predecir(self, D):
        X = self.prep.transform(construir_X(D))
        sobrevive = np.ones(len(X))
        for m in range(4, 13):
            Z = np.column_stack([X, _tramos(np.full(len(X), m))])
            sobrevive *= 1 - self.lr.predict_proba(Z)[:, 1]
        return 1 - sobrevive


class M6Supervivencia(Base):
    nombre = "M6 Supervivencia (tiempo discreto)"

    def ajustar(self, D, ctx):
        self.m, self.elegido = ajustar_con_interno(D, ctx, _Discreto, [0.01, 0.1, 1.0, 10.0])
        return self

    def predecir(self, D):
        return self.m.predecir(D)


# ------------------------------------------------------------------ M7: objetivos auxiliares
class M7Auxiliar(Base):
    def __init__(self, objetivo):
        self.objetivo = objetivo
        self.nombre = f"M7 Auxiliar {objetivo}"

    def ajustar(self, D, ctx):
        A = ctx.permitidas(ctx.auxiliares[self.objetivo], D)
        self.base = M2Penalizada(penalizaciones=(0.0,))
        self.base.ajustar(A, ctx)
        self.elegido = self.base.elegido
        s = logit(np.clip(self.base.predecir(D), EPS, 1 - EPS)).reshape(-1, 1)
        self.recal = LogisticRegression(C=1e6).fit(s, D["y"])
        return self

    def predecir(self, D):
        s = logit(np.clip(self.base.predecir(D), EPS, 1 - EPS)).reshape(-1, 1)
        return self.recal.predict_proba(s)[:, 1]


def bateria():
    """Modelos de la validación principal, en el orden del protocolo."""
    return {"M0a": M0aTasaBase, "M0b": M0bPolitica, "M1": M1Scorecard, "M2": M2Penalizada, "M2F": M2Firth,
            "M3": M3PriorHomeCredit, "M4": M4ApiladoV1, "M5": M5Boosting, "M6": M6Supervivencia,
            "M7_60": lambda: M7Auxiliar("y_60_12m"), "M7_30": lambda: M7Auxiliar("y_30_6m")}


def validar(D, ctx, crear, F, n_jobs=1):
    """Predicciones fuera de pliegue (n_rep × n) y configuración elegida en cada pliegue externo."""
    from joblib import Parallel, delayed

    def uno(r, f):
        te = F[r] == f
        m = crear().ajustar(D[~te], ctx)
        return r, te, m.predecir(D[te]), m.elegido

    res = Parallel(n_jobs=n_jobs)(delayed(uno)(r, f) for r in range(F.shape[0]) for f in np.unique(F[r]))
    P = np.full(F.shape, np.nan)
    elegidos = []
    for r, te, p, e in res:
        P[r, te] = p
        elegidos.append(e)
    return P, elegidos
