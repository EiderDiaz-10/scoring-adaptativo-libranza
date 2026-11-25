"""Ejecuta en orden todos los notebooks de la tesis v2 y los deja guardados con sus salidas.

Uso:  .venv/bin/python correr_todo.py            (todos)
      .venv/bin/python correr_todo.py 02 03      (solo los que empiezan por esos prefijos)
"""
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parent
NOTEBOOKS = sorted((RAIZ / "notebooks").glob("[0-9][0-9]_*.ipynb"))

if __name__ == "__main__":
    filtros = sys.argv[1:]
    for nb_path in NOTEBOOKS:
        if filtros and not any(nb_path.name.startswith(f) for f in filtros):
            continue
        t = time.time()
        nb = nbformat.read(nb_path, as_version=4)
        NotebookClient(nb, timeout=1800, kernel_name="python3",
                       resources={"metadata": {"path": str(nb_path.parent)}}).execute()
        nbformat.write(nb, nb_path)
        print(f"OK  {nb_path.name}  ({time.time() - t:.0f} s)")
