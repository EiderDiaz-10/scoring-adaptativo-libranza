# Despliegue en AWS: cómo hacerlo desde el Mac

Proyecto AWS SAM con la infraestructura completa del score FINTECH (tareas 2 y 3 de `../LEEME_despliegue.md`, ya hechas y probadas):

- **Ingesta:** API Gateway REST con clave de acceso y límite de uso. Rutas `/puntuar` (POST), `/salud` (GET) y `/desenlace` (POST).
- **Modelación:** Lambda en Python 3.12 (arm64) con `scoring.py` y `modelo.json`. Sin dependencias: no necesita Docker.
- **Seguimiento:**
  - DynamoDB cifrado (calificaciones y desenlaces, sin datos personales).
  - Lambda mensual de monitoreo (PSI por bandas y AUC con desenlaces), con reportes en un bucket S3 privado y cifrado.
  - Alarmas de errores, latencia y estabilidad, que avisan por correo.
  - Presupuesto con alerta al 80 %.
  - Registros con retención de 90 días.

Verificado en local: `cfn-lint` sin errores y 9 de 9 pruebas aprobadas (`tests/test_api.py`). Lo desplegado da la misma probabilidad que `prueba_local.py` (tolerancia 1e-6).

**Costo estimado:** menos de USD 1 al mes con el volumen de FINTECH. Lambda y DynamoDB caben en la capa gratuita, y se pagan unos USD 0,30 por las 3 alarmas. La cifra es aproximada: confírmala con la calculadora de AWS.

## 1. Preparar el Mac (una vez)
```bash
brew install awscli aws-sam-cli
aws configure          # pide la clave de acceso de tu usuario IAM (no el raíz), región us-east-1, formato json
aws sts get-caller-identity   # confirma con qué usuario estás conectado
```
El usuario IAM necesita permisos para CloudFormation, Lambda, API Gateway, DynamoDB, S3, IAM (crear roles), CloudWatch, SNS, EventBridge Scheduler y Budgets.

## 2. Empaquetar, probar y construir
```bash
cd "06_despliegue/aws"
./empaquetar.sh                      # copia scoring.py y el modelo final a build_src/ (se niega si el modelo es de ensayo)
python -m pytest -q tests            # 9 pruebas
sam build
```

## 3. Desplegar (crea recursos con costo: hacerlo solo con autorización)
```bash
sam deploy --parameter-overrides CorreoAlertas=tu_correo@dominio.com PresupuestoUSD=10
```
SAM muestra el conjunto de cambios y pide confirmación. Luego, en tu correo, **confirma la suscripción** de AWS SNS para recibir las alertas.

## 4. Probar en la nube
```bash
URL=$(aws cloudformation describe-stacks --stack-name score-fintech --query "Stacks[0].Outputs[?OutputKey=='UrlApi'].OutputValue" --output text)
ID=$(aws cloudformation describe-stacks --stack-name score-fintech --query "Stacks[0].Outputs[?OutputKey=='IdClaveApi'].OutputValue" --output text)
CLAVE=$(aws apigateway get-api-key --api-key $ID --include-value --query value --output text)
curl -s -H "x-api-key: $CLAVE" $URL/salud
python3 -c "import json; d=json.load(open('../modelo_fintech/ejemplo_solicitud.json')); d.pop('_nota'); d['id_solicitud']='PRUEBA-001'; print(json.dumps(d))" > /tmp/sol.json
curl -s -X POST -H "x-api-key: $CLAVE" -H "Content-Type: application/json" -d @/tmp/sol.json $URL/puntuar
```
La probabilidad debe coincidir con la de `python ../modelo_fintech/prueba_local.py`. Guarda las salidas y capturas en `../evidencias/`. La clave del API nunca se escribe en archivos ni en la tesis.

## 5. Cambiar de versión del modelo o borrar todo
- **Nueva versión del modelo:** correr `01_codigo/p9_exportar_modelo.py`, luego `./empaquetar.sh && sam build && sam deploy`.
- **Volver a la versión anterior:** volver a desplegar el `modelo.json` anterior (queda en el historial de la carpeta).
- **Borrar todo:** `sam delete --stack-name score-fintech`. El bucket de reportes debe vaciarse antes.
