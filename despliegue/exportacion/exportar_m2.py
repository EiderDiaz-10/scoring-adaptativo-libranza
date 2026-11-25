"""Exporta M2 (logística L2, modelo elegido de la tesis v2) al formato del servicio de AWS.

Lee solo agregados: resultados/fase4/parametros_modelo_final_M2.csv (parámetros del modelo final ajustado con los
733 créditos de la población primaria) y resultados/fase5/bandas_A_E.csv (cortes de las bandas). Escribe
06_despliegue/artefactos/modelo/modelo.json y ficha_modelo.md. No lee ni escribe filas de clientes.
Uso (desde 07_tesis_v2): python despliegue/exportar_m2.py
"""
import hashlib, json, datetime
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ.parent / "06_despliegue" / "artefactos" / "modelo"
VERSION = "20261115"

par = pd.read_csv(RAIZ / "resultados" / "fase4" / "parametros_modelo_final_M2.csv")
inter = par[par["variable"] == "(intercepto)"].iloc[0]
par = par[par["variable"] != "(intercepto)"]
bandas = pd.read_csv(RAIZ / "resultados" / "fase5" / "bandas_A_E.csv")
m2 = bandas[bandas["modelo"] == "M2"].set_index("banda")
cortes = [float(m2.loc[b, "pd_hasta"]) for b in "ABCD"]
referencia = {b: float(m2.loc[b, "pct_cartera"]) / 100 for b in "ABCDE"}
tabla = pd.read_csv(RAIZ / "resultados" / "fase4" / "tabla_unica_resultados.csv").set_index("modelo")

modelo = {
    "nombre": "score_libranza", "formato": "logistica_nucleo_v2", "version": VERSION,
    "fecha_entrenamiento": "2026-11-15", "modelo": "M2 Logistica L2", "hiperparametros": {"C": 0.1, "penalizacion": "L2"},
    "origen_resultados": "07_tesis_v2 (protocolo v1.1, regla de selección preespecificada)", "es_ensayo": False,
    "producto": "libranza",
    "entrenamiento": {"creditos": 733, "eventos": 23, "tasa_base": 23 / 733,
                      "evento": "90 o más días de mora en los 12 meses desde el desembolso"},
    "metricas_validacion": {"esquema": "StratifiedGroupKFold 5 x 20 por cliente",
                            "auc": float(tabla.loc["M2", "auc"]), "log_loss": float(tabla.loc["M2", "log_loss"]),
                            "pendiente_calibracion": float(tabla.loc["M2", "pendiente_cal"])},
    "entradas": {
        "numericas": ["monto_desembolsado", "plazo_meses", "edad_t0", "n_creditos_previos", "meses_desde_primer_credito",
                      "peor_mora_previa", "n_activos_t0", "emp_creditos_previos"],
        "categoricas": {"cierre_previo": ["sin_previo", "a_termino", "prepago", "con_saldo", "refinanciacion", "otro_o_activo"]},
    },
    "nucleo": [{"variable": r.variable, "mediana": r.mediana_imputacion, "media": r.media, "de": r.de,
                "coef_estandarizado": r.coef_estandarizado} for r in par.itertuples()],
    "intercepto": float(inter["coef_estandarizado"]),
    "recalibracion": {"a": 0.0, "b": 1.0, "nota": "Sin recalibración; la ficha recomienda ajustar el intercepto a la tasa reciente antes de decidir con la PD."},
    "bandas": {"cortes": cortes, "etiquetas": list("ABCDE"), "regla": "relativas a la tasa base p = 3,14 %: 0,5p, p, 2p, 4p",
               "distribucion_referencia": referencia},
}
DESTINO.mkdir(parents=True, exist_ok=True)
texto = json.dumps(modelo, ensure_ascii=False, indent=1)
(DESTINO / "modelo.json").write_text(texto, encoding="utf-8")
huella = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]
ficha = f"""# Ficha del modelo score_libranza v{VERSION}

- Modelo: M2, regresión logística con penalización L2 (C = 0,1), elegida por la regla preespecificada de la tesis v2.
- Población: créditos de libranza; la API rechaza otros productos.
- Evento: 90 o más días de mora en los 12 meses desde el desembolso.
- Entrenamiento: 733 créditos y 23 incumplimientos (2022-2026), sin Home Credit.
- Validación cruzada agrupada 5 x 20: AUC {tabla.loc['M2', 'auc']:.3f}; log loss {tabla.loc['M2', 'log_loss']:.4f} (tasa base 0,1396); pendiente {tabla.loc['M2', 'pendiente_cal']:.2f}.
- La mejora frente a la tasa base no es demostrable; uso previsto: apoyo al analista por bandas, no rechazo automático.
- Bandas (PD): A < {cortes[0]:.4f} ≤ B < {cortes[1]:.4f} ≤ C < {cortes[2]:.4f} ≤ D < {cortes[3]:.4f} ≤ E.
- Reemplaza al modelo v20261107 (tesis v1), guardado en artefactos/_v20261107.
- Huella SHA-256 de modelo.json: {huella}
- Ficha completa: 07_tesis_v2/resultados/fase4/ficha_modelo_v2.md
"""
(DESTINO / "ficha_modelo.md").write_text(ficha, encoding="utf-8")
print("Exportado", modelo["modelo"], VERSION, "huella", huella, "cortes", [round(c, 4) for c in cortes])
