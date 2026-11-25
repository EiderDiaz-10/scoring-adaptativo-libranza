#!/bin/bash
# Prueba del score desplegado en AWS (tarea 5). Guarda la evidencia en ../evidencias sin la clave del API.
set -e
cd "$(dirname "$0")"
PILA=score-fintech
SALIDA="../evidencias/T5_prueba_nube_$(date +%Y%m%d_%H%M).txt"
URL=$(aws cloudformation describe-stacks --stack-name $PILA --query "Stacks[0].Outputs[?OutputKey=='UrlApi'].OutputValue" --output text)
ID=$(aws cloudformation describe-stacks --stack-name $PILA --query "Stacks[0].Outputs[?OutputKey=='IdClaveApi'].OutputValue" --output text)
CLAVE=$(aws apigateway get-api-key --api-key "$ID" --include-value --query value --output text)
SOL=$(python3 -c "import json; d=json.load(open('../modelo_fintech/ejemplo_solicitud.json')); d.pop('_nota',None); d['id_solicitud']='PRUEBA-TESIS-001'; print(json.dumps(d))")
LOCAL=$(cd ../modelo_fintech && python3 -c "import json; from scoring import Modelo; d=json.load(open('ejemplo_solicitud.json')); d.pop('_nota',None); print(Modelo('../artefactos/modelo').puntuar(d)['probabilidad_incumplimiento'])")
pedir() { curl -s -o /tmp/r.json -w "%{http_code} %{time_total}" -H "x-api-key: $CLAVE" -H "Content-Type: application/json" "$@"; }
{
echo "Prueba del score FINTECH desplegado en AWS · $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Pila: $PILA · región us-east-1 · URL: $URL  (la clave del API no se registra)"
echo
echo "[1] GET /salud";                 r=$(pedir "$URL/salud");            echo "    HTTP y segundos: $r"; cat /tmp/r.json; echo
echo "[2] POST /puntuar (solicitud ficticia de ejemplo, primera llamada)"; r=$(pedir -X POST -d "$SOL" "$URL/puntuar"); echo "    HTTP y segundos: $r"; cat /tmp/r.json; echo
NUBE=$(python3 -c "import json; print(json.load(open('/tmp/r.json'))['probabilidad_incumplimiento'])")
echo "    Probabilidad local (prueba_local): $LOCAL · en la nube: $NUBE"
python3 -c "import sys; d=abs($LOCAL-$NUBE); print('    Diferencia:', d, '-> OK' if d<1e-6 else '-> REVISAR')"
echo "[3] Latencia en caliente (5 llamadas)"; for i in 1 2 3 4 5; do r=$(pedir -X POST -d "$SOL" "$URL/puntuar"); echo "    $r"; done
echo "[4] Validación: producto distinto de libranza (debe ser 400)"; r=$(pedir -X POST -d '{"id_solicitud":"PRUEBA-TESIS-002","tipo_producto":"libre_inversion"}' "$URL/puntuar"); echo "    HTTP y segundos: $r"; cat /tmp/r.json; echo
echo "[5] Campos personales se descartan (debe ser 200 sin esos campos)"; r=$(pedir -X POST -d '{"id_solicitud":"PRUEBA-TESIS-003","nombre":"X","documento":"1","edad_t0":30}' "$URL/puntuar"); echo "    HTTP y segundos: $r"; cat /tmp/r.json; echo
echo "[6] Sin clave del API (debe ser 403)"; echo "    HTTP: $(curl -s -o /dev/null -w '%{http_code}' $URL/salud)"
echo "[7] POST /desenlace (retroalimentación ficticia)"; r=$(pedir -X POST -d '{"id_solicitud":"PRUEBA-TESIS-001","dias_mora_max_12m":0,"fecha_corte":"2026-10-31"}' "$URL/desenlace"); echo "    HTTP y segundos: $r"; cat /tmp/r.json; echo
echo "[8] Registro en DynamoDB de la calificación PRUEBA-TESIS-001"
TABLA=$(aws cloudformation describe-stack-resource --stack-name $PILA --logical-resource-id TablaCalificaciones --query StackResourceDetail.PhysicalResourceId --output text)
aws dynamodb get-item --table-name "$TABLA" --key '{"id_solicitud":{"S":"PRUEBA-TESIS-001"}}' --projection-expression "id_solicitud,fecha_calificacion,banda,probabilidad_incumplimiento,version_modelo" --output json
} | tee "$SALIDA"
rm -f /tmp/r.json
echo; echo "Evidencia guardada en $SALIDA"
