#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
else
    echo "No .env file found. Run ./setup-tenants.sh first."
    exit 1
fi

DURATION_MINUTES="${DURATION_MINUTES:-5}"
DURATION_SECONDS=$((DURATION_MINUTES * 60))
ENGINEERING_INTERVAL="${ENGINEERING_INTERVAL:-5}"
MARKETING_INTERVAL="${MARKETING_INTERVAL:-12}"
SUPPORT_INTERVAL="${SUPPORT_INTERVAL:-20}"
MAX_TOKENS_ENGINEERING="${MAX_TOKENS_ENGINEERING:-512}"
MAX_TOKENS_MARKETING="${MAX_TOKENS_MARKETING:-384}"
MAX_TOKENS_SUPPORT="${MAX_TOKENS_SUPPORT:-256}"
MODEL_PRIMARY="${MAAS_MODEL_PRIMARY}"
MODEL_SECONDARY="${MAAS_MODEL_SECONDARY:-$MODEL_PRIMARY}"

# Counters (shared via temp files for cross-process tracking)
STATS_DIR=$(mktemp -d)
echo "0" > "$STATS_DIR/eng_count"
echo "0" > "$STATS_DIR/mkt_count"
echo "0" > "$STATS_DIR/sup_count"
echo "0" > "$STATS_DIR/eng_tokens"
echo "0" > "$STATS_DIR/mkt_tokens"
echo "0" > "$STATS_DIR/sup_tokens"

CLEANUP_DONE=0
cleanup() {
    if [[ $CLEANUP_DONE -eq 1 ]]; then return; fi
    CLEANUP_DONE=1

    kill 0 2>/dev/null || true
    wait 2>/dev/null || true

    echo ""
    echo ""
    echo "================================================"
    echo "  Load Generation Summary"
    echo "================================================"
    echo ""
    printf "  %-15s %8s %12s %8s\n" "Department" "Requests" "Est. Tokens" "Model"
    printf "  %-15s %8s %12s %8s\n" "----------" "--------" "-----------" "-----"
    printf "  %-15s %8s %12s %8s\n" "Engineering" "$(cat "$STATS_DIR/eng_count" 2>/dev/null || echo 0)" "$(cat "$STATS_DIR/eng_tokens" 2>/dev/null || echo 0)" "$MODEL_PRIMARY"
    printf "  %-15s %8s %12s %8s\n" "Marketing" "$(cat "$STATS_DIR/mkt_count" 2>/dev/null || echo 0)" "$(cat "$STATS_DIR/mkt_tokens" 2>/dev/null || echo 0)" "$MODEL_PRIMARY"
    printf "  %-15s %8s %12s %8s\n" "Support" "$(cat "$STATS_DIR/sup_count" 2>/dev/null || echo 0)" "$(cat "$STATS_DIR/sup_tokens" 2>/dev/null || echo 0)" "$MODEL_SECONDARY"
    echo ""
    echo "  Dashboards should now show per-tenant breakdown."
    echo "  Open Perses > Usage to see the chargeback data."
    echo "================================================"
    rm -rf "$STATS_DIR"
}
trap cleanup EXIT INT TERM

send_request() {
    local api_key="$1"
    local model="$2"
    local max_tokens="$3"
    local department="$4"
    local prompt_file="$5"
    local stats_count="$6"
    local stats_tokens="$7"

    local num_prompts
    num_prompts=$(jq length "$prompt_file")
    local idx=$(( RANDOM % num_prompts ))
    local content
    content=$(jq -r ".[$idx].content" "$prompt_file")

    local response
    response=$(curl -s \
        -X POST "${MAAS_GATEWAY}/prelude-maas/${model}/v1/chat/completions" \
        -H "Authorization: Bearer ${api_key}" \
        -H "Content-Type: application/json" \
        -H "User-Agent: dept-${department}" \
        -d "$(jq -n \
            --arg model "$model" \
            --arg content "$content" \
            --argjson max_tokens "$max_tokens" \
            '{
                model: $model,
                messages: [
                    {role: "system", content: "You are a helpful AI assistant working for a large enterprise."},
                    {role: "user", content: $content}
                ],
                max_tokens: $max_tokens,
                stream: false
            }')" 2>/dev/null || echo '{}')

    local total_tokens
    total_tokens=$(echo "$response" | jq -r '.usage.total_tokens // 0' 2>/dev/null || echo "0")

    # Update counters
    local current_count
    current_count=$(cat "$stats_count")
    echo $((current_count + 1)) > "$stats_count"

    local current_tokens
    current_tokens=$(cat "$stats_tokens")
    echo $((current_tokens + total_tokens)) > "$stats_tokens"

    local timestamp
    timestamp=$(date +%H:%M:%S)
    printf "  [%s] %-13s  %5s tokens  (%s)\n" "$timestamp" "$department" "$total_tokens" "$model"
}

run_tenant_load() {
    local api_key="$1"
    local model="$2"
    local max_tokens="$3"
    local department="$4"
    local interval="$5"
    local prompt_file="$6"
    local stats_count="$7"
    local stats_tokens="$8"

    local end_time=$((SECONDS + DURATION_SECONDS))

    while [[ $SECONDS -lt $end_time ]]; do
        send_request "$api_key" "$model" "$max_tokens" "$department" "$prompt_file" "$stats_count" "$stats_tokens"
        local jitter=$(( (RANDOM % interval) + (interval / 2) ))
        sleep "$jitter"
    done
}

echo "================================================"
echo "  AI Chargeback Demo - Load Generator"
echo "================================================"
echo ""
echo "  Duration:     ${DURATION_MINUTES} minutes"
echo "  Engineering:  every ~${ENGINEERING_INTERVAL}s  (${MODEL_PRIMARY}, ${MAX_TOKENS_ENGINEERING} max tokens)"
echo "  Marketing:    every ~${MARKETING_INTERVAL}s  (${MODEL_PRIMARY}, ${MAX_TOKENS_MARKETING} max tokens)"
echo "  Support:      every ~${SUPPORT_INTERVAL}s  (${MODEL_SECONDARY}, ${MAX_TOKENS_SUPPORT} max tokens)"
echo ""
echo "  Traffic ratio: ~60% engineering / ~25% marketing / ~15% support"
echo ""
echo "  Press Ctrl+C to stop early and see summary."
echo ""
echo "  Live requests:"
echo ""

# Launch 3 tenant streams in parallel
run_tenant_load "$API_KEY_ENGINEERING" "$MODEL_PRIMARY" "$MAX_TOKENS_ENGINEERING" \
    "engineering" "$ENGINEERING_INTERVAL" "$SCRIPT_DIR/prompts/engineering.json" \
    "$STATS_DIR/eng_count" "$STATS_DIR/eng_tokens" &

run_tenant_load "$API_KEY_MARKETING" "$MODEL_PRIMARY" "$MAX_TOKENS_MARKETING" \
    "marketing" "$MARKETING_INTERVAL" "$SCRIPT_DIR/prompts/marketing.json" \
    "$STATS_DIR/mkt_count" "$STATS_DIR/mkt_tokens" &

run_tenant_load "$API_KEY_SUPPORT" "$MODEL_SECONDARY" "$MAX_TOKENS_SUPPORT" \
    "support" "$SUPPORT_INTERVAL" "$SCRIPT_DIR/prompts/support.json" \
    "$STATS_DIR/sup_count" "$STATS_DIR/sup_tokens" &

wait
