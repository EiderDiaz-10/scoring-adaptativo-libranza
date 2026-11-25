"""Calificación de una solicitud con el modelo exportado (v2: 07_tesis_v2/despliegue/exportar_m2.py; v1: 01_codigo/p9_exportar_modelo.py).

Uso:
    from scoring import Modelo
    m = Modelo("artefactos/modelo")          # carpeta con modelo.json (y xgb_m*.json si el modelo es XGBoost)
    m.puntuar({"edad_t0": 35, "monto_desembolsado": 8000000, ...})
    -> {"probabilidad_incumplimiento": 0.043, "probabilidad_sin_recalibrar": 0.051, "banda": "B", ...}

Reproduce exactamente las transformaciones del entrenamiento (Paso 5 `formatear` y Paso 6 `Diseno`):
percentiles frente a la distribución de FINTECH, indicadores, estandarización, one-hot y promedio de las versiones.
Python puro para la logística y la red (sin dependencias, apto para AWS Lambda sin capas); numpy y xgboost solo si
el modelo elegido es XGBoost. No guarda ni envía datos de la solicitud.
"""
import json, math
from bisect import bisect_right
from pathlib import Path


def _interp(x, xs, ys):
    """Interpolación lineal como numpy.interp (fuera del rango devuelve el extremo)."""
    if x <= xs[0]: return ys[0]
    if x >= xs[-1]: return ys[-1]
    i = bisect_right(xs, x) - 1
    if xs[i] == x or xs[i + 1] == xs[i]: return ys[i]
    return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])

BINARIAS_ENTRADA = ["sin_historial_buro", "en_mora_actual", "correo_registrado", "cobra_aval_seguro", "fin_de_semana",
                    "dispositivo_movil", "correo_mal_escrito", "nombre_en_correo", "numeros_en_correo", "uso_copiar_pegar",
                    "abandono_parcial"]


ADVERSOS, FAVORABLES = ("con_saldo", "refinanciacion"), ("a_termino", "prepago")


class ModeloNucleo:
    """Formato logistica_nucleo_v2 (tesis v2, M2): 11 predictores construidos igual que diseno.construir_X."""

    def __init__(self, M):
        self.M = M
        self.ENTRADAS = M["entradas"]["numericas"] + list(M["entradas"]["categoricas"])
        self.NUM, self.BIN, self.CAT = M["entradas"]["numericas"], [], list(M["entradas"]["categoricas"])

    @staticmethod
    def _num(x):
        try:
            x = float(x)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    def preparar(self, s):
        g = lambda k, *alt: next((self._num(s.get(c)) for c in (k, *alt) if s.get(c) is not None), None)
        monto, plazo, edad = g("monto_desembolsado", "monto"), g("plazo_meses"), g("edad_t0")
        npre, meses, mora = g("n_creditos_previos"), g("meses_desde_primer_credito"), g("peor_mora_previa")
        activos, emp = g("n_activos_t0"), g("emp_creditos_previos")
        cierre = s.get("cierre_previo")
        hist = None if npre is None else npre > 0
        x = {
            "log_monto": None if monto is None else math.log(max(monto, 1e5)),
            "log_plazo": None if plazo is None else math.log(max(plazo, 1)),
            "edad_t0": edad,
            "tiene_historia": None if hist is None else float(hist),
            "log_n_previos": None if npre is None else math.log1p(npre),
            "meses_cliente": 0.0 if hist is False else meses,
            "log_peor_mora_previa": 0.0 if hist is False else (None if mora is None else math.log1p(max(mora, 0))),
            "previo_adverso": float(cierre in ADVERSOS),
            "previo_favorable": float(cierre in FAVORABLES),
            "n_activos_t0": activos,
            "log_emp_previos": math.log1p(emp or 0.0),      # en el entrenamiento el faltante es 0 (sin créditos previos)
        }
        return x, [k for k in self.ENTRADAS if s.get(k) is None and not (k == "monto_desembolsado" and s.get("monto") is not None)]

    def puntuar(self, solicitud):
        x, faltan = self.preparar(dict(solicitud))
        z = self.M["intercepto"]
        for v in self.M["nucleo"]:
            val = x[v["variable"]]
            val = v["mediana"] if val is None else val                   # imputación por la mediana del entrenamiento
            z += v["coef_estandarizado"] * (val - v["media"]) / (v["de"] or 1.0)
        p = 1 / (1 + math.exp(-z))
        r = self.M["recalibracion"]; lg = math.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))
        pc = 1 / (1 + math.exp(-(r["a"] + r["b"] * lg)))
        banda = self.M["bandas"]["etiquetas"][sum(pc >= c for c in self.M["bandas"]["cortes"])]
        return {"probabilidad_incumplimiento": round(pc, 6), "probabilidad_sin_recalibrar": round(p, 6), "banda": banda,
                "modelo": self.M["modelo"], "version_modelo": self.M["version"], "variables_faltantes": faltan}


class Modelo:
    def __new__(cls, carpeta):
        M = json.loads((Path(carpeta) / "modelo.json").read_text(encoding="utf-8"))
        if M.get("formato") == "logistica_nucleo_v2":
            return ModeloNucleo(M)
        return super().__new__(cls)

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.M = json.loads((self.carpeta / "modelo.json").read_text(encoding="utf-8"))
        self.NUM, self.BIN, self.CAT = (self.M["variables"][k] for k in ("NUM", "BIN", "CAT"))
        self._xgb = {}
        if self.M["modelo"] == "Boosting_XGBoost":
            import xgboost as xgb
            for ver in self.M["versiones"]:
                b = xgb.Booster(); b.load_model(str(self.carpeta / ver["xgboost"])); self._xgb[ver["version"]] = b

    # -------------------------------------------------------- variables derivadas (Paso 5)
    def _num(self, x):
        try:
            x = float(x)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    def preparar(self, s):
        """Solicitud en bruto (dict) -> dict con las variables del modelo. Lo que falta queda en None."""
        f = {}
        refs, origen = self.M["percentiles"]["referencias"], self.M["percentiles"]["origen"]
        sal = self._num(s.get("salario_mensual"))
        if s.get("valor_en_mora_sobre_salario") is None and sal and self._num(s.get("valor_en_mora_pesos")) is not None:
            s = {**s, "valor_en_mora_sobre_salario": self._num(s["valor_en_mora_pesos"]) / sal}
        for v_pct, v in origen.items():                                  # percentil frente a FINTECH (como rank pct)
            if self._num(s.get(v_pct)) is not None:                      # ya viene como percentil (0 a 1)
                f[v_pct] = self._num(s[v_pct]); continue
            x, r = self._num(s.get(v)), refs[v_pct]                      # tabla valor -> percentil de FINTECH
            f[v_pct] = None if x is None or not r["valores"] else float(_interp(x, r["valores"], r["percentiles"]))
        for v in self.NUM:
            if v not in f and v != "log_tiempo_diligenciamiento": f[v] = self._num(s.get(v))
        t = self._num(s.get("tiempo_diligenciamiento_seg"))
        f["log_tiempo_diligenciamiento"] = None if t is None else math.log1p(t)
        cast = self._num(s.get("castigos"))
        f["tiene_castigos"] = None if cast is None else float(cast > 0)
        npre = self._num(s.get("n_creditos_previos"))
        f["sin_creditos_previos"] = None if npre is None else float(npre == 0)
        for b in BINARIAS_ENTRADA:
            x = s.get(b); f[b] = None if x is None else float(bool(x) if isinstance(x, bool) else self._num(x) or 0.0)
        for c in self.CAT:
            f[c] = None if s.get(c) is None else str(s.get(c))
        return f

    # -------------------------------------------------------- diseño (Paso 6) y modelos
    def _fila(self, f, ver):
        d = ver["diseno"]; x = []
        for v in self.NUM:
            val = f.get(v); val = d["med"][v] if val is None else val
            x.append((val - d["mu"][v]) / (d["sd"][v] or 1.0))
        x.append(1.0 if f.get("peor_mora_previa") is None else 0.0)       # falta_peor_mora_previa
        x += [0.0 if f.get(b) is None else float(f[b]) for b in self.BIN]
        for c in self.CAT:
            x += [1.0 if f.get(c) == k else 0.0 for k in d["cats"][c][1:]]
        x.append(0.0)                                                     # fuente_hc = 0: la solicitud es de FINTECH
        assert len(x) == len(ver["columnas"]), "el diseño no coincide con las columnas del entrenamiento"
        return x

    def _prob(self, x, ver):
        if "logistica" in ver:
            z = sum(c * v for c, v in zip(ver["logistica"]["coef"], x)) + ver["logistica"]["intercepto"]
            return 1 / (1 + math.exp(-z))
        if "red" in ver:
            a = list(x)
            for i, capa in enumerate(ver["red"]):
                a = [sum(w * v for w, v in zip(fila, a)) + b for fila, b in zip(capa["W"], capa["b"])]
                if i < len(ver["red"]) - 1: a = [max(v, 0.0) for v in a]
            return 1 / (1 + math.exp(-a[0]))
        import numpy as np, xgboost as xgb
        return float(self._xgb[ver["version"]].predict(xgb.DMatrix(np.array([x], dtype=np.float32), feature_names=ver["columnas"]))[0])

    def puntuar(self, solicitud):
        f = self.preparar(dict(solicitud))
        ps = [self._prob(self._fila(f, ver), ver) for ver in self.M["versiones"]]; p = sum(ps) / len(ps)
        lg = math.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))
        r = self.M["recalibracion"]; pc = 1 / (1 + math.exp(-(r["a"] + r["b"] * lg)))
        banda = self.M["bandas"]["etiquetas"][sum(pc > c for c in self.M["bandas"]["cortes"])]
        faltan = [v for v in self.NUM + self.BIN + self.CAT if f.get(v) is None]
        return {"probabilidad_incumplimiento": round(pc, 6), "probabilidad_sin_recalibrar": round(p, 6), "banda": banda,
                "modelo": self.M["modelo"], "version_modelo": self.M["version"], "variables_faltantes": faltan}
