"""Verifica que el servicio (scoring.py + modelo.json) reproduce el M2 final ajustado con scikit-learn.
Corre en el equipo; no escribe filas de clientes (solo imprime diferencias agregadas)."""
import sys, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src")); sys.path.insert(0, str(RAIZ.parent / "06_despliegue" / "modelo_fintech"))
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from tesis_v2 import contexto, diseno
from scoring import Modelo

D, ctx, ds = contexto.cargar()
pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.1, max_iter=5000))
pipe.fit(diseno.construir_X(D), D["y"])
p_sk = pipe.predict_proba(diseno.construir_X(D))[:, 1]
m = Modelo(RAIZ.parent / "06_despliegue" / "artefactos" / "modelo")
campos = ["monto", "plazo_meses", "edad_t0", "n_creditos_previos", "meses_desde_primer_credito", "peor_mora_previa",
          "cierre_previo", "n_activos_t0", "emp_creditos_previos"]
p_api = []
for _, r in D[campos].iterrows():
    s = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()}
    s["monto_desembolsado"] = s.pop("monto"); s["cierre_previo"] = str(s["cierre_previo"])
    p_api.append(m.puntuar(s)["probabilidad_sin_recalibrar"])
d = np.abs(np.array(p_api) - p_sk)
print(f"créditos {len(D)} · diferencia máxima {d.max():.2e} · media {d.mean():.2e} · PD media {p_sk.mean():.4f}")
assert d.max() < 1e-4, "el servicio no reproduce el modelo"
print("OK: el servicio reproduce M2")
