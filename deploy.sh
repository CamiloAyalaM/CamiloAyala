#!/usr/bin/env bash
# deploy.sh — Importa los workflows actualizados a n8n via API
# Uso: N8N_API_KEY=<tu-key> ./deploy.sh
#
# API Key: n8n → Settings → n8n API → Create an API key

set -euo pipefail

N8N_HOST="${N8N_HOST:-https://n8n.camiloayala.net}"
API_KEY="${N8N_API_KEY:-}"
WORKFLOWS_DIR="$(cd "$(dirname "$0")/workflows" && pwd)"

if [[ -z "$API_KEY" ]]; then
  echo "❌  Falta N8N_API_KEY. Ejecútalo así:"
  echo "    N8N_API_KEY=tu-api-key ./deploy.sh"
  exit 1
fi

# Workflows a desplegar: nombre exacto en n8n → archivo local
declare -A WORKFLOWS=(
  ["[MA] REPORTER — Indexador de Informes LinkedIn"]="[MA] REPORTER — Indexador de Informes LinkedIn.json"
  ["[MA] REPORTER — Drive Watcher"]="[MA] REPORTER — Drive Watcher.json"
  ["[MA] COMMANDS — Bot Dispatcher"]="[MA] COMMANDS — Bot Dispatcher (1).json"
  ["[MA] ANALYST — Métricas y Feedback"]="[MA] ANALYST — Métricas y Feedback.json"
  ["[MA] WRITER — Motor 3 Pasos"]="[MA] WRITER — Motor 3 Pasos.json"
)

echo "🔍  Obteniendo lista de workflows desde $N8N_HOST..."
RESPONSE=$(curl -sf \
  -H "X-N8N-API-KEY: $API_KEY" \
  -H "Accept: application/json" \
  "$N8N_HOST/api/v1/workflows?limit=100")

if [[ -z "$RESPONSE" ]]; then
  echo "❌  No se pudo conectar a la API. Verifica N8N_HOST y N8N_API_KEY."
  exit 1
fi

SUCCESS=0
FAILED=0

for WORKFLOW_NAME in "${!WORKFLOWS[@]}"; do
  FILE="${WORKFLOWS[$WORKFLOW_NAME]}"
  FILE_PATH="$WORKFLOWS_DIR/$FILE"

  if [[ ! -f "$FILE_PATH" ]]; then
    echo "⚠️   Archivo no encontrado: $FILE — saltando"
    ((FAILED++)) || true
    continue
  fi

  # Buscar ID por nombre (búsqueda parcial segura con jq)
  WORKFLOW_ID=$(echo "$RESPONSE" | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('data', data) if isinstance(data, dict) else data
name = sys.argv[1]
for w in items:
    if w.get('name','') == name:
        print(w['id'])
        break
" "$WORKFLOW_NAME" 2>/dev/null || true)

  if [[ -z "$WORKFLOW_ID" ]]; then
    echo "⚠️   No encontrado en n8n: \"$WORKFLOW_NAME\" — saltando"
    ((FAILED++)) || true
    continue
  fi

  echo "📤  Actualizando \"$WORKFLOW_NAME\" (id: $WORKFLOW_ID)..."

  # Leer el JSON del archivo y extraer solo nodes+connections+settings
  PAYLOAD=$(python3 -c "
import sys, json
with open(sys.argv[1]) as f:
    wf = json.load(f)
# n8n API PUT espera el objeto completo del workflow
print(json.dumps(wf))
" "$FILE_PATH")

  HTTP_CODE=$(curl -s -o /tmp/n8n_response.json -w "%{http_code}" \
    -X PUT \
    -H "X-N8N-API-KEY: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$N8N_HOST/api/v1/workflows/$WORKFLOW_ID")

  if [[ "$HTTP_CODE" == "200" ]]; then
    echo "   ✅  Actualizado correctamente"
    ((SUCCESS++)) || true
  else
    echo "   ❌  Error HTTP $HTTP_CODE:"
    cat /tmp/n8n_response.json | python3 -m json.tool 2>/dev/null || cat /tmp/n8n_response.json
    ((FAILED++)) || true
  fi
done

echo ""
echo "═══════════════════════════════"
echo "✅  Actualizados: $SUCCESS"
[[ $FAILED -gt 0 ]] && echo "❌  Fallidos:     $FAILED"
echo "═══════════════════════════════"
echo ""
echo "⚠️   Recuerda reactivar los workflows si estaban activos:"
echo "    n8n UI → workflow → toggle ON"
