"""Componente adaptativo / incremental (Fase 6).

Distingo dos cosas que la v1 mezclaba:

1. **Reentrenamiento por lotes** con disparadores (calendario, conteo de eventos, PSI).
2. **Aprendizaje en línea** (actualizar con cada crédito): no es lo que simulo aquí.

La simulación es *prequential* / origen móvil: en cada origen solo uso créditos cuyo
desenlace ya es conocido (fecha de conocimiento = t0 + 13 meses). El mecanismo natural
de actualización es el de M3: un *prior* centrado en el modelo vigente, con τ que crece
con los eventos propios para soltar el ancla cuando hay evidencia nueva.

Versión 1.2 (enmienda v1.2, 15-nov-2026, tras la auditoría):
- La estrategia bayesiana actualiza SOLO con los créditos cuyo desenlace se conoció desde la
  actualización anterior; el prior es el posterior anterior (media y varianza de Laplace, diagonal),
  inflado por un factor de olvido fijado a priori. Así ningún dato se cuenta dos veces.
- C (estático, expansivo, ponderado) y τ inicial (bayesiano) se eligen en cada ajuste con un 3-fold
  interno agrupado sobre los datos conocidos en ese corte, no con los de la Fase 4 (que usaban todo).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import config, estadistica as est
from .diseno import COMPARTIDAS, NUCLEO, construir_X
from .modelos import map_logistica

EPS = 1e-6
MESES_CONOCIMIENTO = 13  # 12 meses de ventana + 1 de demora operativa
C_M2 = 0.1               # hiperparámetro del modelo elegido (ficha v2)
TAU0 = 0.25              # τ inicial (óptimo de la Fase 4 para M3)
N0_EVENTOS = 10          # eventos propios con los que τ se duplica
MIN_EVENTOS_ENTRENA = 5  # por debajo no cabe una logística estable
PSI_UMBRAL = 0.25
FACTOR_OLVIDO = 1.25     # la varianza del prior se multiplica por este factor en cada actualización
GRILLA_C_L2 = list(np.logspace(-3, 1, 7))
TAUS = (0.25, 0.5, 1.0, 2.0, 4.0)
VARS_PSI = ["log_monto", "log_emp_previos", "edad_t0", "log_plazo"]


def fecha_conocimiento(t0: pd.Series, meses: int = MESES_CONOCIMIENTO) -> pd.Series:
    """Fecha en la que el desenlace a 12 meses se considera conocido."""
    return pd.to_datetime(t0) + pd.DateOffset(months=meses)


def preparar(D: pd.DataFrame) -> pd.DataFrame:
    """Añade fechas de conocimiento y marcas de periodo sin tocar las filas."""
    out = D.copy()
    out["t0"] = pd.to_datetime(out["t0"])
    out["conocimiento"] = fecha_conocimiento(out["t0"])
    out["trimestre_conocimiento"] = out["conocimiento"].dt.to_period("Q").astype(str)
    return out.sort_values(["t0", "cid"]).reset_index(drop=True)


def trimestres_origen(D: pd.DataFrame) -> list[str]:
    return sorted(D["trimestre_t0"].unique())


def inicio_trimestre(periodo: str) -> pd.Timestamp:
    return pd.Period(periodo, freq="Q").start_time


def entrenamiento_conocido(D: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Créditos cuyo desenlace ya es conocido en `corte` (sin fuga temporal)."""
    return D[D["conocimiento"] < corte].reset_index(drop=True)


def prueba_origen(D: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    return D[D["trimestre_t0"] == trimestre].reset_index(drop=True)


# ------------------------------------------------------------------ ajuste puntual (sin CV anidada)
@dataclass
class ModeloPuntual:
    """Logística estandarizada con coeficientes en unidades naturales y estandarizadas."""
    nombre: str
    b0: float
    b_std: np.ndarray
    b_nat: np.ndarray
    mediana: np.ndarray
    media: np.ndarray
    de: np.ndarray
    n: int
    eventos: int
    tau: float | None = None

    def predecir(self, D: pd.DataFrame) -> np.ndarray:
        X = construir_X(D).to_numpy(float)
        X = np.where(np.isnan(X), self.mediana, X)
        Z = (X - self.media) / np.where(self.de > 0, self.de, 1.0)
        return expit(self.b0 + Z @ self.b_std)


def _estadisticos(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mediana = np.nanmedian(X, axis=0)
    Xc = np.where(np.isnan(X), mediana, X)
    media = Xc.mean(axis=0)
    de = Xc.std(axis=0, ddof=0)
    de = np.where(de > 0, de, 1.0)
    return mediana, media, de


def ajustar_m2(D: pd.DataFrame, C: float = C_M2) -> ModeloPuntual:
    X = construir_X(D).to_numpy(float)
    y = D["y"].to_numpy(float)
    mediana, media, de = _estadisticos(X)
    Z = (np.where(np.isnan(X), mediana, X) - media) / de
    lr = LogisticRegression(C=C, solver="lbfgs", max_iter=5000)
    lr.fit(Z, y)
    b_std = lr.coef_[0]
    return ModeloPuntual("M2", float(lr.intercept_[0]), b_std, b_std / de, mediana, media, de,
                         len(D), int(y.sum()))


def ajustar_m2_ponderado(D: pd.DataFrame, pesos: np.ndarray, C: float = C_M2) -> ModeloPuntual:
    X = construir_X(D).to_numpy(float)
    y = D["y"].to_numpy(float)
    mediana, media, de = _estadisticos(X)
    Z = (np.where(np.isnan(X), mediana, X) - media) / de
    lr = LogisticRegression(C=C, solver="lbfgs", max_iter=5000)
    w = pesos * len(pesos) / pesos.sum()
    lr.fit(Z, y, sample_weight=w)
    b_std = lr.coef_[0]
    return ModeloPuntual("M2pond", float(lr.intercept_[0]), b_std, b_std / de, mediana, media, de,
                         len(D), int(y.sum()))


def tau_por_eventos(n_eventos: int, tau0: float = TAU0, n0: int = N0_EVENTOS) -> float:
    """τ crece con la raíz de los eventos propios: más datos → prior más laxo."""
    return float(tau0 * np.sqrt(1.0 + max(n_eventos, 0) / n0))


def ajustar_map(D: pd.DataFrame, mu_nat: np.ndarray, tau: float) -> ModeloPuntual:
    """MAP con prior N(μ_nat · DE, τ²) en escala estandarizada; intercepto plano."""
    X = construir_X(D).to_numpy(float)
    y = D["y"].to_numpy(float)
    mediana, media, de = _estadisticos(X)
    Z = (np.where(np.isnan(X), mediana, X) - media) / de
    mu = mu_nat * de
    b0, b_std, _ = map_logistica(Z, y, mu, tau)
    return ModeloPuntual("MAP", float(b0), b_std, b_std / de, mediana, media, de,
                         len(D), int(y.sum()), tau=tau)


def mu_desde_hc(beta_hc: pd.Series) -> np.ndarray:
    """Centro del prior de Home Credit en unidades naturales (0 si no hay equivalente)."""
    mu = np.zeros(len(NUCLEO))
    for j, v in enumerate(NUCLEO):
        if v in COMPARTIDAS and v in beta_hc.index:
            mu[j] = float(beta_hc[v])
    return mu



def _desde_pipeline(nombre: str, pipe, D: pd.DataFrame) -> ModeloPuntual:
    imp, esc, lr = pipe[0], pipe[1], pipe[-1]
    b_std = lr.coef_[0]
    return ModeloPuntual(nombre, float(lr.intercept_[0]), b_std, b_std / esc.scale_, imp.statistics_.astype(float),
                         esc.mean_.astype(float), esc.scale_.astype(float), len(D), int(D["y"].sum()))


def ajustar_m2_interno(D: pd.DataFrame, ctx, pesos: np.ndarray | None = None, nombre: str = "M2") -> ModeloPuntual:
    """M2-L2 con C elegido en un 3-fold interno agrupado solo con los datos conocidos en el corte."""
    from .modelos import _Logistica, ajustar_con_interno
    m, cfg = ajustar_con_interno(D, ctx, lambda c: _Logistica(c), [(C, 0.0) for C in GRILLA_C_L2])
    if pesos is not None:                      # reajuste ponderado con el C elegido
        X = construir_X(D)
        w = pesos * len(pesos) / pesos.sum()
        m.pipe.fit(X, D["y"], logisticregression__sample_weight=w)
    out = _desde_pipeline(nombre, m.pipe, D)
    out.tau = None
    out.C = float(cfg[0])
    return out


def _map_completo(Z: np.ndarray, y: np.ndarray, m: np.ndarray, v: np.ndarray):
    """MAP con prior normal independiente sobre intercepto y coeficientes; devuelve (θ, covarianza de Laplace)."""
    from scipy.optimize import minimize
    X1 = np.column_stack([np.ones(len(Z)), Z])

    def f(th):
        z = X1 @ th
        val = np.sum(np.logaddexp(0, z) - y * z) + np.sum((th - m) ** 2 / (2 * v))
        grad = X1.T @ (expit(z) - y) + (th - m) / v
        return val, grad

    th = minimize(f, m.copy(), jac=True, method="L-BFGS-B").x
    p = expit(X1 @ th)
    H = X1.T @ (X1 * (p * (1 - p))[:, None]) + np.diag(1 / v)
    return th, np.linalg.inv(H)


def ajustar_bayes_inicial(D: pd.DataFrame, ctx) -> ModeloPuntual:
    """Primer ajuste: M3 (prior de Home Credit) con τ elegido en el pliegue interno."""
    from .modelos import _Prior, ajustar_con_interno
    m, tau = ajustar_con_interno(D, ctx, lambda t: _Prior(t, True), list(TAUS))
    imp, esc = m.prep[0], m.prep[-1]
    out = ModeloPuntual("Bayes", float(m.b0), m.b, m.b / esc.scale_, imp.statistics_.astype(float),
                        esc.mean_.astype(float), esc.scale_.astype(float), len(D), int(D["y"].sum()), tau=float(tau))
    out.cov = m.cov
    return out


def actualizar_bayes(prev: ModeloPuntual, lote: pd.DataFrame, factor: float | None = None) -> ModeloPuntual:
    """Actualización secuencial: verosimilitud solo del lote nuevo; prior = posterior anterior inflado."""
    factor = FACTOR_OLVIDO if factor is None else factor
    if len(lote) == 0:
        return prev
    X = construir_X(lote).to_numpy(float)
    Z = (np.where(np.isnan(X), prev.mediana, X) - prev.media) / prev.de     # estandarización fija del inicio
    m = np.concatenate([[prev.b0], prev.b_std])
    v = np.diag(prev.cov) * factor
    th, cov = _map_completo(Z, lote["y"].to_numpy(float), m, v)
    out = ModeloPuntual("Bayes", float(th[0]), th[1:], th[1:] / prev.de, prev.mediana, prev.media, prev.de,
                        prev.n + len(lote), prev.eventos + int(lote["y"].sum()), tau=prev.tau)
    out.cov = cov
    return out

# ------------------------------------------------------------------ estrategias
@dataclass
class EstadoEstrategia:
    nombre: str
    modelo: ModeloPuntual | None = None
    actualizaciones: list = field(default_factory=list)
    eventos_desde_update: int = 0
    eventos_en_ultimo: int = 0
    referencia_psi: pd.DataFrame | None = None


def pesos_exponenciales(conocimiento: pd.Series, corte: pd.Timestamp, vida_media_meses: float = 18.0) -> np.ndarray:
    """Peso que decae a la mitad cada `vida_media_meses` respecto a la fecha de conocimiento."""
    meses = (corte - conocimiento).dt.days.to_numpy(float) / 30.4375
    return np.exp(-np.log(2) * np.clip(meses, 0, None) / vida_media_meses)


def actualizar(estado: EstadoEstrategia, train: pd.DataFrame, corte: pd.Timestamp,
               beta_hc: pd.Series | None, modo: str, ctx=None, lote: pd.DataFrame | None = None) -> EstadoEstrategia:
    """Ajusta el modelo de la estrategia con lo conocido en `corte` (v1.2: C y τ por pliegue interno)."""
    ev = int(train["y"].sum())
    if ev < MIN_EVENTOS_ENTRENA:
        return estado
    reg = {"corte": str(corte.date()), "eventos": ev, "n": len(train)}
    if modo == "tasa_base":                     # referencia: predice la tasa conocida en el corte
        k = len(NUCLEO); tasa = float(np.clip(train["y"].mean(), EPS, 1 - EPS))
        estado.modelo = ModeloPuntual("Tasa", float(np.log(tasa / (1 - tasa))), np.zeros(k), np.zeros(k),
                                      np.zeros(k), np.zeros(k), np.ones(k), len(train), ev)
        estado.actualizaciones.append({**reg, "C": None, "tau": None})
        return estado
    if modo == "estatico":
        if estado.modelo is None:
            estado.modelo = ajustar_m2_interno(train, ctx)
            estado.actualizaciones.append({**reg, "C": estado.modelo.C, "tau": None})
        return estado
    if modo == "expansivo":
        estado.modelo = ajustar_m2_interno(train, ctx)
        estado.actualizaciones.append({**reg, "C": estado.modelo.C, "tau": None})
        return estado
    if modo == "ponderado":
        w = pesos_exponenciales(train["conocimiento"], corte)
        estado.modelo = ajustar_m2_interno(train, ctx, pesos=w, nombre="M2pond")
        estado.actualizaciones.append({**reg, "C": estado.modelo.C, "tau": None})
        return estado
    if modo == "bayes_secuencial":
        if estado.modelo is None:
            estado.modelo = ajustar_bayes_inicial(train, ctx)
        else:
            estado.modelo = actualizar_bayes(estado.modelo, lote if lote is not None else train.iloc[0:0])
        estado.actualizaciones.append({**reg, "C": None, "tau": estado.modelo.tau, "n_lote": 0 if lote is None else len(lote)})
        return estado
    raise ValueError(modo)


# ------------------------------------------------------------------ disparadores
def psi_predictores(ref: pd.DataFrame, act: pd.DataFrame, variables=VARS_PSI) -> dict[str, float]:
    Xr, Xa = construir_X(ref), construir_X(act)
    return {v: est.psi(Xr[v], Xa[v]) for v in variables}


def psi_puntaje(ref_p: np.ndarray, act_p: np.ndarray) -> float:
    return est.psi(pd.Series(ref_p), pd.Series(act_p))


def evaluar_disparadores(estado: EstadoEstrategia, train: pd.DataFrame, lote_nuevo: pd.DataFrame,
                         umbral_psi: float = PSI_UMBRAL, cada_eventos: int = 10) -> dict:
    """Evalúa si el calendario (siempre en la simulación trimestral), el conteo o el PSI disparan."""
    ev_nuevos = int(lote_nuevo["y"].sum()) if len(lote_nuevo) else 0
    estado.eventos_desde_update += ev_nuevos
    out = {
        "eventos_nuevos": ev_nuevos,
        "eventos_acumulados_desde_update": estado.eventos_desde_update,
        "disparo_eventos": estado.eventos_desde_update >= cada_eventos,
        "disparo_psi": False,
        "psi_max": 0.0,
        "psi_detalle": {},
    }
    if estado.modelo is not None and len(lote_nuevo) >= 20:
        det = psi_predictores(train if estado.referencia_psi is None else estado.referencia_psi, lote_nuevo)
        out["psi_detalle"] = det
        out["psi_max"] = float(max(det.values())) if det else 0.0
        out["disparo_psi"] = out["psi_max"] > umbral_psi
        if estado.modelo is not None and len(train) >= 30:
            pref = estado.modelo.predecir(train)
            pact = estado.modelo.predecir(lote_nuevo)
            out["psi_puntaje"] = psi_puntaje(pref, pact)
            out["disparo_psi"] = out["disparo_psi"] or out["psi_puntaje"] > umbral_psi
    return out


# ------------------------------------------------------------------ simulación prequential
def simular_prequential(D: pd.DataFrame, beta_hc: pd.Series | None = None,
                        estrategias: dict | None = None,
                        cada_eventos: int = 10, ctx=None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Origen móvil trimestral con fecha de conocimiento a 13 meses.

    Devuelve:
    - predicciones agregadas (una fila por crédito × estrategia);
    - bitácora de actualizaciones y disparadores;
    - estados finales.
    """
    D = preparar(D)
    estrategias = estrategias or {
        "tasa_base": "tasa_base",
        "estatico": "estatico",
        "expansivo": "expansivo",
        "ponderado": "ponderado",
        "bayes_secuencial": "bayes_secuencial",
    }
    estados = {k: EstadoEstrategia(nombre=k) for k in estrategias}
    ultimo_corte = {k: None for k in estrategias}
    preds, bitacora = [], []
    origenes = trimestres_origen(D)

    for i, q in enumerate(origenes):
        corte = inicio_trimestre(q)
        train = entrenamiento_conocido(D, corte)
        test = prueba_origen(D, q)
        # Lote de desenlaces que maduraron desde el origen anterior (para disparadores)
        if i == 0:
            lote = train.iloc[0:0]
        else:
            corte_prev = inicio_trimestre(origenes[i - 1])
            lote = D[(D["conocimiento"] >= corte_prev) & (D["conocimiento"] < corte)]

        for nombre, modo in estrategias.items():
            disp = evaluar_disparadores(estados[nombre], train, lote, cada_eventos=cada_eventos)
            # Política de disparo en la simulación:
            # - estático: solo la primera vez que hay eventos suficientes
            # - resto: calendario trimestral (y además registro de PSI/eventos)
            debe = (modo == "estatico" and estados[nombre].modelo is None) or (modo != "estatico")
            if debe and int(train["y"].sum()) >= MIN_EVENTOS_ENTRENA:
                uc = ultimo_corte[nombre]
                lote_propio = train.iloc[0:0] if uc is None else D[(D["conocimiento"] >= uc) & (D["conocimiento"] < corte)]
                actualizar(estados[nombre], train, corte, beta_hc, modo, ctx=ctx, lote=lote_propio)
                ultimo_corte[nombre] = corte
                if modo != "estatico":
                    estados[nombre].eventos_desde_update = 0
                    estados[nombre].referencia_psi = train.copy()
            bitacora.append({
                "origen": q, "estrategia": nombre, "corte": str(corte.date()),
                "n_train": len(train), "eventos_train": int(train["y"].sum()),
                "n_test": len(test), "eventos_test": int(test["y"].sum()) if len(test) else 0,
                "actualizo": estados[nombre].modelo is not None and debe and int(train["y"].sum()) >= MIN_EVENTOS_ENTRENA,
                "tau": estados[nombre].modelo.tau if estados[nombre].modelo else None,
                **{k: disp[k] for k in ("eventos_nuevos", "eventos_acumulados_desde_update",
                                        "disparo_eventos", "disparo_psi", "psi_max")},
                "psi_puntaje": disp.get("psi_puntaje"),
            })
            if estados[nombre].modelo is None or len(test) == 0:
                continue
            p = estados[nombre].modelo.predecir(test)
            for j in range(len(test)):
                preds.append({
                    "estrategia": nombre, "origen": q, "cid": int(test.loc[j, "cid"]),
                    "grupo_cliente": test.loc[j, "grupo_cliente"],
                    "y": int(test.loc[j, "y"]), "p": float(p[j]),
                    "t0": test.loc[j, "t0"], "conocimiento": test.loc[j, "conocimiento"],
                })

    return pd.DataFrame(preds), pd.DataFrame(bitacora), estados


def metricas_por_estrategia(preds: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for nombre, g in preds.groupby("estrategia"):
        y, p = g["y"].to_numpy(), g["p"].to_numpy()
        ll = float(-np.mean(y * np.log(np.clip(p, EPS, 1 - EPS)) + (1 - y) * np.log(np.clip(1 - p, EPS, 1 - EPS))))
        br = float(np.mean((p - y) ** 2))
        prev = y.mean()
        auc = float(roc_auc_score(y, p)) if y.sum() > 0 and y.sum() < len(y) else np.nan
        filas.append({
            "estrategia": nombre, "n": len(g), "eventos": int(y.sum()), "tasa": float(prev),
            "log_loss": ll, "brier": br, "brier_escalado": 1 - br / (prev * (1 - prev) + EPS),
            "auc": auc, "pd_media": float(p.mean()),
        })
    return pd.DataFrame(filas)


def metricas_por_origen(preds: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (estrategia, origen), g in preds.groupby(["estrategia", "origen"]):
        y, p = g["y"].to_numpy(), g["p"].to_numpy()
        auc = float(roc_auc_score(y, p)) if y.sum() > 0 and (1 - y).sum() > 0 else np.nan
        ll = float(-np.mean(y * np.log(np.clip(p, EPS, 1 - EPS)) + (1 - y) * np.log(np.clip(1 - p, EPS, 1 - EPS))))
        filas.append({"estrategia": estrategia, "origen": origen, "n": len(g),
                      "eventos": int(y.sum()), "auc": auc, "log_loss": ll, "pd_media": float(p.mean())})
    return pd.DataFrame(filas)


def bootstrap_pareado(preds: pd.DataFrame, a: str, b: str, B: int = 2000,
                      semilla: int = config.SEMILLA) -> dict:
    """Δ log loss y Δ AUC entre dos estrategias, remuestreando clientes."""
    pa = preds[preds["estrategia"] == a].set_index("cid")
    pb = preds[preds["estrategia"] == b].set_index("cid")
    comunes = pa.index.intersection(pb.index)
    pa, pb = pa.loc[comunes], pb.loc[comunes]
    y = pa["y"].to_numpy()
    grupos = pa["grupo_cliente"].to_numpy()
    unicos = np.unique(grupos)
    rng = np.random.default_rng(semilla)
    d_ll, d_auc = [], []
    for _ in range(B):
        sel = rng.choice(unicos, size=len(unicos), replace=True)
        idx = np.concatenate([np.flatnonzero(grupos == g) for g in sel])
        ya, pa_, pb_ = y[idx], pa["p"].to_numpy()[idx], pb["p"].to_numpy()[idx]
        if ya.sum() == 0 or ya.sum() == len(ya):
            continue
        lla = -np.mean(ya * np.log(np.clip(pa_, EPS, 1 - EPS)) + (1 - ya) * np.log(np.clip(1 - pa_, EPS, 1 - EPS)))
        llb = -np.mean(ya * np.log(np.clip(pb_, EPS, 1 - EPS)) + (1 - ya) * np.log(np.clip(1 - pb_, EPS, 1 - EPS)))
        d_ll.append(lla - llb)
        d_auc.append(roc_auc_score(ya, pa_) - roc_auc_score(ya, pb_))
    d_ll, d_auc = np.asarray(d_ll), np.asarray(d_auc)

    def res(d, est_puntual):
        lo, hi = np.percentile(d, [2.5, 97.5])
        p = float(min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean())))
        return {"delta": est_puntual, "ic_inf": float(lo), "ic_sup": float(hi), "p": p}

    # puntuales
    lla = -np.mean(y * np.log(np.clip(pa["p"], EPS, 1 - EPS)) + (1 - y) * np.log(np.clip(1 - pa["p"], EPS, 1 - EPS)))
    llb = -np.mean(y * np.log(np.clip(pb["p"], EPS, 1 - EPS)) + (1 - y) * np.log(np.clip(1 - pb["p"], EPS, 1 - EPS)))
    auca = roc_auc_score(y, pa["p"])
    aucb = roc_auc_score(y, pb["p"])
    return {
        "a": a, "b": b,
        "log_loss": res(d_ll, float(lla - llb)),
        "auc": res(d_auc, float(auca - aucb)),
        "n_comunes": int(len(comunes)), "eventos": int(y.sum()),
    }


# ------------------------------------------------------------------ potencia hacia adelante
def potencia_adelante(eventos_actuales: int, no_eventos_actuales: int, prevalencia: float,
                      auc_ref: float = 0.65, deltas=(0.05, 0.08, 0.10, 0.15),
                      eventos_por_anio: float = 6.0, r: float = 0.5) -> pd.DataFrame:
    """Eventos (y años) necesarios para detectar una mejora de AUC con 80 % de potencia."""
    from scipy import stats
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    filas = []
    for d in deltas:
        e_necesario = None
        se_en = np.nan
        for e in range(max(eventos_actuales, 5), 5000):
            n0 = max(1, int(e / prevalencia - e))
            se = est.se_auc_hanley(auc_ref, e, n0)
            se_d = np.sqrt(2 * se ** 2 * (1 - r))
            if z * se_d <= d:
                e_necesario, se_en = e, float(se_d)
                break
        if e_necesario is None:
            continue
        adicionales = max(0, e_necesario - eventos_actuales)
        filas.append({
            "delta_auc": d, "eventos_necesarios": e_necesario,
            "eventos_adicionales": adicionales,
            "anios_aprox": adicionales / eventos_por_anio if eventos_por_anio > 0 else np.nan,
            "se_delta_en_necesarios": se_en,
        })
    se_act = est.se_auc_hanley(auc_ref, eventos_actuales, no_eventos_actuales)
    se_d_act = np.sqrt(2 * se_act ** 2 * (1 - r))
    for f in filas:
        f["potencia_actual_%"] = float(100 * stats.norm.cdf(f["delta_auc"] / se_d_act - 1.96))
    return pd.DataFrame(filas)


def tasa_eventos_anual(D: pd.DataFrame) -> float:
    """Media de eventos por año de originación en la población primaria."""
    D = preparar(D)
    por_anio = D.groupby(D["t0"].dt.year)["y"].sum()
    # Excluyo el último año incompleto si tiene 0 eventos y pocos créditos
    if len(por_anio) >= 2 and por_anio.iloc[-1] == 0:
        por_anio = por_anio.iloc[:-1]
    return float(por_anio.mean())
