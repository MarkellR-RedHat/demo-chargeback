#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${NAMESPACE:-$(oc project -q 2>/dev/null || echo 'default')}"

echo "================================================"
echo "  AI Chargeback Demo - Deploy on Cluster"
echo "================================================"
echo ""
echo "  Namespace: $NAMESPACE"
echo ""

# Check oc is logged in
if ! oc whoami &>/dev/null; then
    echo "[ERROR] Not logged into OpenShift. Run: oc login ..."
    exit 1
fi
echo "[OK] Logged in as $(oc whoami)"

# Load .env
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "[OK] Loaded .env"
else
    echo "[ERROR] No .env file. Copy .env.example to .env and fill in your values."
    exit 1
fi

# Validate required vars
MLFLOW_INTERNAL="${MLFLOW_INTERNAL_URI:-https://mlflow.redhat-ods-applications.svc.cluster.local:8443}"
WORKSPACE="${MLFLOW_WORKSPACE:-$NAMESPACE}"
GATEWAY="${MAAS_GATEWAY:?MAAS_GATEWAY not set in .env}"
MODEL_PRIMARY="${MAAS_MODEL_PRIMARY:?MAAS_MODEL_PRIMARY not set in .env}"
MODEL_SECONDARY="${MAAS_MODEL_SECONDARY:-$MODEL_PRIMARY}"
ALIAS_PRIMARY="${MLFLOW_MODEL_ALIAS_PRIMARY:-$MODEL_PRIMARY}"
ALIAS_SECONDARY="${MLFLOW_MODEL_ALIAS_SECONDARY:-$MODEL_SECONDARY}"

echo ""
echo "  Configuration:"
echo "    Gateway:     $GATEWAY"
echo "    Models:      $MODEL_PRIMARY / $MODEL_SECONDARY"
echo "    Cost alias:  $ALIAS_PRIMARY / $ALIAS_SECONDARY"
echo "    MLflow:      $MLFLOW_INTERNAL"
echo "    Workspace:   $WORKSPACE"
echo "    Duration:    ${DURATION_MINUTES:-5} min"
echo ""

# Step 1: Secret
echo "Step 1: Creating API key secret..."
oc create secret generic chargeback-demo-keys \
    --from-literal=API_KEY_ENGINEERING="${API_KEY_ENGINEERING}" \
    --from-literal=API_KEY_MARKETING="${API_KEY_MARKETING}" \
    --from-literal=API_KEY_SUPPORT="${API_KEY_SUPPORT}" \
    --dry-run=client -o yaml | oc apply -f -
echo "[OK] Secret created"

# Step 2: Code configmap
echo ""
echo "Step 2: Creating code configmap..."
oc create configmap chargeback-demo-code \
    --from-file=generate-load.py="$SCRIPT_DIR/generate-load.py" \
    --dry-run=client -o yaml | oc apply -f -
echo "[OK] Code configmap created"

# Step 3: Prompts configmap
echo ""
echo "Step 3: Creating prompts configmap..."
oc apply -f "$SCRIPT_DIR/k8s/configmap-prompts.yaml"
echo "[OK] Prompts configmap created"

# Step 4: MLflow RBAC
echo ""
echo "Step 4: Creating MLflow rolebinding..."
oc apply -f "$SCRIPT_DIR/k8s/rolebinding-mlflow.yaml" 2>/dev/null || \
    echo "[WARN] RoleBinding may already exist or ClusterRole not found."
echo "[OK] RoleBinding applied"

# Step 5: Generate and apply job with values from .env
echo ""
echo "Step 5: Deploying load generator job..."
oc delete job chargeback-demo-load --ignore-not-found 2>/dev/null

cat <<EOF | oc apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: chargeback-demo-load
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      initContainers:
        - name: merge-ca
          image: registry.access.redhat.com/ubi9/ubi-minimal:latest
          command: ["sh", "-c"]
          args:
            - |
              cat /etc/pki/tls/certs/ca-bundle.crt > /ca-out/combined-ca.crt || true
              cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt >> /ca-out/combined-ca.crt 2>/dev/null || true
              cat /var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt >> /ca-out/combined-ca.crt 2>/dev/null || true
              echo "CA bundle ready"
          volumeMounts:
            - name: ca-bundle
              mountPath: /ca-out
      containers:
        - name: load-generator
          image: registry.access.redhat.com/ubi9/python-311:latest
          command: ["sh", "-c"]
          args:
            - |
              pip install --quiet 'mlflow[genai]==3.10.1' openai python-dotenv &&
              cd /app &&
              python generate-load.py --duration \${DURATION_MINUTES} --experiment \${MLFLOW_EXPERIMENT_NAME} --split-experiments
          env:
            - name: MAAS_GATEWAY
              value: "${GATEWAY}"
            - name: MAAS_MODEL_PRIMARY
              value: "${MODEL_PRIMARY}"
            - name: MAAS_MODEL_SECONDARY
              value: "${MODEL_SECONDARY}"
            - name: MLFLOW_MODEL_ALIAS_PRIMARY
              value: "${ALIAS_PRIMARY}"
            - name: MLFLOW_MODEL_ALIAS_SECONDARY
              value: "${ALIAS_SECONDARY}"
            - name: API_KEY_ENGINEERING
              valueFrom:
                secretKeyRef:
                  name: chargeback-demo-keys
                  key: API_KEY_ENGINEERING
            - name: API_KEY_MARKETING
              valueFrom:
                secretKeyRef:
                  name: chargeback-demo-keys
                  key: API_KEY_MARKETING
            - name: API_KEY_SUPPORT
              valueFrom:
                secretKeyRef:
                  name: chargeback-demo-keys
                  key: API_KEY_SUPPORT
            - name: MLFLOW_TRACKING_URI
              value: "${MLFLOW_INTERNAL}"
            - name: MLFLOW_TRACKING_TOKEN_FILE
              value: "/var/run/secrets/kubernetes.io/serviceaccount/token"
            - name: MLFLOW_WORKSPACE
              value: "${WORKSPACE}"
            - name: MLFLOW_EXPERIMENT_NAME
              value: "ai-chargeback-demo"
            - name: REQUESTS_CA_BUNDLE
              value: "/ca-out/combined-ca.crt"
            - name: DURATION_MINUTES
              value: "${DURATION_MINUTES:-5}"
            - name: ENGINEERING_INTERVAL
              value: "${ENGINEERING_INTERVAL:-5}"
            - name: MARKETING_INTERVAL
              value: "${MARKETING_INTERVAL:-12}"
            - name: SUPPORT_INTERVAL
              value: "${SUPPORT_INTERVAL:-20}"
            - name: MAX_TOKENS_ENGINEERING
              value: "${MAX_TOKENS_ENGINEERING:-512}"
            - name: MAX_TOKENS_MARKETING
              value: "${MAX_TOKENS_MARKETING:-384}"
            - name: MAX_TOKENS_SUPPORT
              value: "${MAX_TOKENS_SUPPORT:-256}"
          volumeMounts:
            - name: app-code
              mountPath: /app
            - name: prompts
              mountPath: /app/prompts
            - name: ca-bundle
              mountPath: /ca-out
      volumes:
        - name: app-code
          configMap:
            name: chargeback-demo-code
        - name: prompts
          configMap:
            name: chargeback-demo-prompts
        - name: ca-bundle
          emptyDir: {}
EOF

echo "[OK] Job created"

# Step 6: Follow logs
echo ""
echo "================================================"
echo "  Job deployed. Waiting for pod to start..."
echo "================================================"
echo ""

for i in $(seq 1 30); do
    POD=$(oc get pods -l job-name=chargeback-demo-load -o name 2>/dev/null | head -1 || true)
    if [[ -n "$POD" ]]; then
        STATUS=$(oc get "$POD" -o jsonpath='{.status.phase}' 2>/dev/null || echo "unknown")
        if [[ "$STATUS" != "Pending" ]]; then
            break
        fi
    fi
    echo "  Waiting for pod... ($i/30)"
    sleep 5
done

if [[ -n "$POD" ]]; then
    echo "  Pod: $POD (status: $STATUS)"
    echo ""
    echo "  Following logs (Ctrl+C to detach, job continues running):"
    echo ""
    oc logs -f "$POD" --all-containers 2>/dev/null || echo "  (logs not yet available, try: oc logs -f $POD --all-containers)"
else
    echo "[WARN] Pod not started after 2.5 minutes. Check with:"
    echo "  oc get pods -l job-name=chargeback-demo-load"
    echo "  oc describe job chargeback-demo-load"
fi
