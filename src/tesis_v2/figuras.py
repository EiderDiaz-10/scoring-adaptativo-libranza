"""Estilo único de figuras para la tesis: sobrio, legible en blanco y negro y exportado en PNG (300 ppp) y PDF."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402

AZUL, NARANJA, VERDE, GRIS, ROJO = "#1f4e79", "#d9822b", "#2e8b57", "#7f7f7f", "#b22222"
SECUENCIA = ["#1f4e79", "#d9822b", "#2e8b57", "#8e44ad", "#7f7f7f", "#b22222"]


def _ruta_catalogo(fase: str):
    return config.RESULTADOS / fase / "catalogo_figuras.json"


def estilo():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "font.family": "DejaVu Sans", "font.size": 9,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "legend.frameon": False,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "figure.facecolor": "white",
    })


def guardar(fig, fase: str, codigo: str, nombre: str, mensaje: str):
    """Guarda la figura y registra su mensaje de una línea en el catálogo de la fase."""
    base = config.FIGURAS / fase / f"{codigo}_{nombre}"
    fig.savefig(base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    # El catálogo se guarda en disco porque las figuras de una fase vienen de varios notebooks (varios kernels).
    ruta = _ruta_catalogo(fase)
    catalogo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    catalogo[codigo] = {"archivo": f"figuras/{fase}/{codigo}_{nombre}.png", "mensaje": mensaje}
    ruta.write_text(json.dumps(dict(sorted(catalogo.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    plt.show()
    plt.close(fig)


def escribir_catalogo(fase: str, titulo: str):
    ruta = _ruta_catalogo(fase)
    catalogo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    lineas = [f"# {titulo}", "", "| Código | Archivo | Mensaje |", "|---|---|---|"]
    lineas += [f"| {c} | `{f['archivo']}` | {f['mensaje']} |" for c, f in sorted(catalogo.items())]
    path = config.RESULTADOS / fase / "catalogo_figuras.md"
    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return path
