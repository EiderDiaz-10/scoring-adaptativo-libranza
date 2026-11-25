"""Lectura de insumos con trazabilidad (hash SHA-256) y guardado seguro de salidas."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

_INSUMOS: dict[str, str] = {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_parquet(path: Path, columnas: list[str] | None = None) -> pd.DataFrame:
    path = Path(path)
    _INSUMOS[str(path.relative_to(config.PROYECTO))] = sha256(path)
    return pd.read_parquet(path, columns=columnas)


def leer_tabla(nombre: str, columnas: list[str] | None = None) -> pd.DataFrame:
    """Lee una tabla del export de FINTECH sin columnas de identificación personal."""
    path = config.EXPORT_FINTECH / f"bd_{nombre}.parquet"
    if columnas is None:
        import pyarrow.parquet as pq
        columnas = [c for c in pq.read_schema(path).names if c not in config.COLUMNAS_PII]
    return leer_parquet(path, columnas)


def insumos_leidos() -> dict[str, str]:
    return dict(_INSUMOS)


# ---------------------------------------------------------------- conversión de tipos
def llave(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").round().astype("Int64")


def numero(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def fecha(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


# ---------------------------------------------------------------- salidas
def verificar_sin_pii(df: pd.DataFrame, permitir_ids: bool = False) -> None:
    """Falla si una tabla que va a resultados/ trae columnas personales o llaves de cliente."""
    cols = {str(c).lower() for c in df.columns} | {str(i).lower() for i in (df.index.names or []) if i}
    malas = cols & config.COLUMNAS_PII
    if not permitir_ids:
        malas |= cols & {"cliente_id", "cli", "empresa_id", "emp"}
    if malas:
        raise ValueError(f"La tabla contiene columnas no publicables: {sorted(malas)}")


def guardar_resultado(df: pd.DataFrame, fase: str, nombre: str, index: bool = False) -> Path:
    """Guarda una tabla agregada en resultados/<fase>/ como CSV (UTF-8, separador coma)."""
    verificar_sin_pii(df)
    path = config.RESULTADOS / fase / f"{nombre}.csv"
    df.to_csv(path, index=index, encoding="utf-8")
    return path


def guardar_privado(df: pd.DataFrame, nombre: str) -> Path:
    path = config.PRIVADO / f"{nombre}.parquet"
    df.to_parquet(path, index=False)
    return path


def escribir_registro(nombre: str, contenido: dict) -> Path:
    """Registro de reproducibilidad en evidencias/: versiones, semilla, insumos y salidas con hash."""
    meta = {
        "paso": nombre,
        "fecha_ejecucion": datetime.now().isoformat(timespec="seconds"),
        "semilla": config.SEMILLA,
        "versiones": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "insumos_sha256": insumos_leidos(),
        **contenido,
    }
    path = config.EVIDENCIAS / f"registro_{nombre}.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
