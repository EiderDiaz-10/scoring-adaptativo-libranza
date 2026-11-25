#!/bin/bash
# Califica una solicitud en el modelo desplegado en AWS y explica la respuesta.
# Uso:  ./probar.sh                      (solicitud de ejemplo, bajo riesgo)
#       ./probar.sh ../modelo_fintech/ejemplo_riesgoso.json
#       ./probar.sh mi_solicitud.json    (copia de un ejemplo con tus valores; solo datos ficticios)
set -e
cd "$(dirname "$0")"
ARCH="${1:-../modelo_fintech/ejemplo_solicitud.json}"
PILA=score-fintech
URL=$(aws cloudformation describe-stacks --stack-name $PILA --query "Stacks[0].Outputs[?OutputKey=='UrlApi'].OutputValue" --output text)
ID=$(aws cloudformation describe-stacks --stack-name $PILA --query "Stacks[0].Outputs[?OutputKey=='IdClaveApi'].OutputValue" --output text)
CLAVE=$(aws apigateway get-api-key --api-key "$ID" --include-value --query value --output text)
SOL=$(python3 -c "import json,sys,time; d=json.load(open(sys.argv[1])); d.pop('_nota',None); d['id_solicitud']='PRUEBA-'+time.strftime('%Y%m%d-%H%M%S'); print(json.dumps(d))" "$ARCH")
echo "Enviando $ARCH al modelo en AWS..."
RESP=$(curl -s -H "x-api-key: $CLAVE" -H "Content-Type: application/json" -X POST -d "$SOL" "$URL/puntuar")
echo; echo "Respuesta del modelo:"; echo "$RESP" | python3 -m json.tool
python3 - "$RESP" <<'P'
import json,sys
r=json.loads(sys.argv[1])
if "error" in r: print("\nLa solicitud fue rechazada:", r.get("detalle")); sys.exit()
txt={"A":"riesgo muy bajo","B":"riesgo bajo","C":"riesgo medio","D":"riesgo medio-alto","E":"riesgo alto (en la prueba 2025+, rechazar E evitaba el 70 % de los incumplimientos)"}
p=r["probabilidad_incumplimiento"]
print(f"\nEn palabras: la probabilidad de que este crédito llegue a más de 90 días de mora en 12 meses es {p*100:.1f} %.")
print(f"Banda {r['banda']}: {txt[r['banda']]}.")
f=r.get("variables_faltantes",[])
print("Todas las variables llegaron." if not f else f"Faltaron {len(f)} variables (se usó el valor típico): {', '.join(f[:8])}{' ...' if len(f)>8 else ''}")
print(f"Modelo: {r['modelo']}, versión {r['version_modelo']}. Calificación registrada con id {r['id_solicitud']}.")
P
