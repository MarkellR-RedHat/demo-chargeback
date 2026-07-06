#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "  AI Chargeback Demo - Tenant Setup"
echo "================================================"
echo ""

# Load environment
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "[OK] Loaded .env"
else
    echo "[ERROR] No .env file found. Copy .env.example to .env and fill in your values."
    echo "  cp .env.example .env"
    exit 1
fi

# Validate required vars
missing=0
for var in MAAS_GATEWAY MAAS_MODEL_PRIMARY API_KEY_ENGINEERING API_KEY_MARKETING API_KEY_SUPPORT; do
    if [[ -z "${!var:-}" ]]; then
        echo "[MISSING] $var is not set"
        missing=1
    fi
done
if [[ $missing -eq 1 ]]; then
    echo ""
    echo "Set the missing variables in .env and re-run."
    exit 1
fi

echo ""
echo "Tenant configuration:"
echo "  Gateway:    $MAAS_GATEWAY"
echo "  Primary:    $MAAS_MODEL_PRIMARY"
echo "  Secondary:  ${MAAS_MODEL_SECONDARY:-$MAAS_MODEL_PRIMARY}"
echo ""
echo "  Engineering API key: ${API_KEY_ENGINEERING:0:8}..."
echo "  Marketing API key:   ${API_KEY_MARKETING:0:8}..."
echo "  Support API key:     ${API_KEY_SUPPORT:0:8}..."
echo ""

# Connectivity check for each tenant
echo "Testing gateway connectivity per tenant..."
for tenant in ENGINEERING MARKETING SUPPORT; do
    key_var="API_KEY_${tenant}"
    key="${!key_var}"
    model="$MAAS_MODEL_PRIMARY"
    if [[ "$tenant" == "SUPPORT" && -n "${MAAS_MODEL_SECONDARY:-}" ]]; then
        model="$MAAS_MODEL_SECONDARY"
    fi

    tenant_lower=$(echo "$tenant" | tr '[:upper:]' '[:lower:]')

    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${MAAS_GATEWAY}/prelude-maas/${model}/v1/chat/completions" \
        -H "Authorization: Bearer ${key}" \
        -H "Content-Type: application/json" \
        -H "User-Agent: dept-${tenant_lower}" \
        -d "{
            \"model\": \"${model}\",
            \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}],
            \"max_tokens\": 5,
            \"stream\": false
        }" 2>/dev/null || echo "000")

    if [[ "$response" == "200" ]]; then
        echo "  [OK] ${tenant_lower} -> ${model} (HTTP 200)"
    else
        echo "  [WARN] ${tenant_lower} -> ${model} (HTTP ${response})"
        echo "         Check API key and model availability."
    fi
done

echo ""
echo "Prompt files:"
for f in engineering marketing support; do
    count=$(jq length "$SCRIPT_DIR/prompts/${f}.json" 2>/dev/null || echo "?")
    echo "  prompts/${f}.json: ${count} prompts"
done

echo ""
echo "================================================"
echo "  Setup complete. Run ./generate-load.sh to"
echo "  start generating multi-tenant traffic."
echo "================================================"
