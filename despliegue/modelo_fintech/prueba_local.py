"""Prueba local del modelo exportado: python prueba_local.py  (desde 06_despliegue/modelo_fintech)."""
import json, time
from pathlib import Path
from scoring import Modelo
AQUI = Path(__file__).resolve().parent
m = Modelo(AQUI.parent / "artefactos" / "modelo")
sol = json.loads((AQUI / "ejemplo_solicitud.json").read_text(encoding="utf-8"))
t = time.time(); r = m.puntuar(sol)
print(json.dumps(r, ensure_ascii=False, indent=2)); print(f"Tiempo: {1000 * (time.time() - t):.1f} ms")
assert 0 <= r["probabilidad_incumplimiento"] <= 1 and r["banda"] in "ABCDE"
r2 = m.puntuar({k: v for k, v in sol.items() if k.startswith(("edad", "monto", "plazo", "tipo"))})   # solicitud incompleta
print("Con datos incompletos:", r2["probabilidad_incumplimiento"], r2["banda"], "· faltan", len(r2["variables_faltantes"]), "variables")
print("OK")
