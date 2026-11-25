#!/bin/bash
# Arma build_src/ con los manejadores, la función de calificación y el modelo exportado. Correr antes de "sam build".
set -e
cd "$(dirname "$0")"
rm -rf build_src && mkdir -p build_src/modelo
cp app/*.py build_src/
cp ../modelo_fintech/scoring.py build_src/
cp ../artefactos/modelo/modelo.json ../artefactos/modelo/ficha_modelo.md build_src/modelo/
ls ../artefactos/modelo/xgb_m*.json >/dev/null 2>&1 && cp ../artefactos/modelo/xgb_m*.json build_src/modelo/ || true
python3 -c "import json; m=json.load(open('build_src/modelo/modelo.json')); assert not m.get('es_ensayo'), 'El modelo es de ensayo: no se despliega'; print('Paquete listo:', m['modelo'], 'versión', m['version'])"
