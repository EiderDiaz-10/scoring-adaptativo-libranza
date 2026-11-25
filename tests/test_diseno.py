"""Pruebas anti-fuga de la Fase 3 (criterios de aceptación del plan).

Usan datos sintéticos con la misma estructura del dataset analítico, para que puedan ejecutarse
y compartirse sin tocar datos de clientes. Ejecutar con: .venv/bin/python -m pytest tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tesis_v2 import diseno, modelos  # noqa: E402


def sinteticos(n=400, semilla=1):
    rng = np.random.default_rng(semilla)
    grupos = rng.integers(0, n // 2, n)
    prev = rng.poisson(0.8, n)
    d = pd.DataFrame({
        "grupo_cliente": grupos, "monto": rng.lognormal(15, 0.6, n), "plazo_meses": rng.uniform(6, 48, n),
        "edad_t0": np.where(rng.random(n) < 0.02, np.nan, rng.uniform(20, 70, n)),
        "n_creditos_previos": prev, "n_activos_t0": np.minimum(prev, rng.integers(0, 2, n)),
        "peor_mora_previa": np.where(prev > 0, rng.exponential(10, n), np.nan),
        "meses_desde_primer_credito": np.where(prev > 0, rng.uniform(1, 40, n), np.nan),
        "cierre_previo": np.where(prev > 0, rng.choice(["a_termino", "con_saldo", "prepago", "otro_o_activo"], n),
                                  "sin_previo"),
        "emp_creditos_previos": rng.integers(0, 300, n).astype(float),
        "tiempo_90": rng.uniform(30, 600, n),
    })
    z = -3 + 0.8 * (d["peor_mora_previa"].fillna(0) > 15) - 0.01 * (d["edad_t0"].fillna(40) - 40)
    d["y"] = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    d["evento_90"] = d["y"]
    return d


def test_ningun_cliente_en_dos_pliegues():
    d = sinteticos()
    F = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=5)
    for r in range(F.shape[0]):
        pliegues_por_grupo = pd.Series(F[r]).groupby(d["grupo_cliente"].to_numpy()).nunique()
        assert (pliegues_por_grupo == 1).all()


def test_particiones_reproducibles_por_semilla():
    d = sinteticos()
    a = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=3, semilla=7)
    b = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=3, semilla=7)
    c = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=3, semilla=8)
    assert (a == b).all() and not (a == c).all()


def test_predictores_son_fila_a_fila():
    """Cambiar filas de prueba no altera los predictores de las filas de entrenamiento."""
    d = sinteticos()
    alterado = d.copy()
    alterado.loc[:99, ["monto", "edad_t0", "peor_mora_previa"]] *= 7
    pd.testing.assert_frame_equal(diseno.construir_X(d).iloc[100:], diseno.construir_X(alterado).iloc[100:])


@pytest.mark.parametrize("clave", ["M1", "M2", "M3", "M5"])
def test_prediccion_de_prueba_no_depende_de_la_prueba(clave):
    """Alterar desenlace y predictores del pliegue de prueba no cambia el modelo ajustado."""
    d = sinteticos()
    X_hc = diseno.construir_X_home_credit(pd.DataFrame({
        "edad_t0": d["edad_t0"].fillna(40), "plazo_meses": d["plazo_meses"], "n_creditos_previos": d["n_creditos_previos"],
        "antiguedad_cliente_meses": d["meses_desde_primer_credito"], "peor_mora_previa": d["peor_mora_previa"]}))
    ctx = modelos.Contexto(grupos_primarios=set(d["grupo_cliente"]), beta_hc=modelos.beta_home_credit(X_hc, d["y"]))
    F = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=1)
    te = F[0] == 0
    crear = modelos.bateria()[clave]
    p1 = crear().ajustar(d[~te], ctx).predecir(d[te])
    alterado = d.copy()
    alterado.loc[te, "y"] = 1 - alterado.loc[te, "y"]
    alterado.loc[te, "monto"] *= 3
    p2 = crear().ajustar(alterado[~te], ctx).predecir(d[te])
    np.testing.assert_allclose(p1, p2)


def test_woe_no_usa_el_desenlace_de_prueba():
    d = sinteticos()
    S = diseno.construir_scorecard(d)
    w1 = diseno.WoE(4).fit(S.iloc[:300], d["y"].iloc[:300]).transform(S.iloc[300:])
    y2 = d["y"].copy()
    y2.iloc[300:] = 1 - y2.iloc[300:]
    w2 = diseno.WoE(4).fit(S.iloc[:300], y2.iloc[:300]).transform(S.iloc[300:])
    np.testing.assert_array_equal(w1, w2)


def test_filas_extra_excluyen_clientes_de_prueba():
    d = sinteticos()
    ctx = modelos.Contexto(grupos_primarios=set(d["grupo_cliente"]))
    F = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=1)
    te = F[0] == 0
    extra = ctx.permitidas(d, d[~te])
    assert not set(extra["grupo_cliente"]) & set(d.loc[te, "grupo_cliente"])


def test_supervivencia_no_ve_clientes_de_prueba():
    d = sinteticos()
    ctx = modelos.Contexto(grupos_primarios=set(d["grupo_cliente"]), supervivencia=d)
    F = diseno.particiones(d["grupo_cliente"], d["y"], n_rep=1)
    te = F[0] == 0
    p1 = modelos._Discreto(1.0).ajustar(d[~te], ctx).predecir(d[te])
    alterado = d.copy()
    alterado.loc[te, "evento_90"] = 1
    alterado.loc[te, "tiempo_90"] = 130.0
    ctx2 = modelos.Contexto(grupos_primarios=set(d["grupo_cliente"]), supervivencia=alterado)
    p2 = modelos._Discreto(1.0).ajustar(d[~te], ctx2).predecir(d[te])
    np.testing.assert_allclose(p1, p2)
