# AI Chargeback Demo

Answers the question: **"What did AI cost us this quarter, by department?"**

This demo simulates three business units (Engineering, Marketing, Support) consuming a shared AI inference platform on Red Hat OpenShift AI. It generates realistic multi-tenant traffic and populates observability dashboards with per-department token usage, model cost attribution, and GPU utilization data.

## Architecture

```
                          ┌──────────────────────────────────────────────────────┐
                          │              Red Hat OpenShift AI Cluster            │
                          │                                                      │
┌──────────────┐          │  ┌────────────────┐      ┌─────────────────────┐     │
│  Engineering │─(API Key)──▶│                │      │  vLLM / llm-d       │     │
│  60% traffic │          │  │  MaaS Gateway  │─────▶│  gemma4 (primary)   │     │
└──────────────┘          │  │  (API Gateway) │      │  qwen35-9b (secondary)    │
┌──────────────┐          │  │                │      └─────────┬───────────┘     │
│  Marketing   │─(API Key)──▶│  Routes by     │                │                │
│  25% traffic │          │  │  model + key   │                │ metrics         │
└──────────────┘          │  └────────────────┘                ▼                │
┌──────────────┐          │         │                 ┌─────────────────┐       │
│  Support     │─(API Key)──▶       │                 │   Prometheus    │       │
│  15% traffic │          │         │ traces          │   (COO)         │       │
└──────────────┘          │         ▼                 └────────┬────────┘       │
                          │  ┌────────────────┐                │                │
 generate-load.py ────────── │    MLflow       │       ┌───────▼────────┐       │
 (token + cost traces)    │  │  (Experiment    │       │    Perses      │       │
                          │  │   Tracking)     │       │  Usage Dashboard│      │
                          │  └────────────────┘       └────────────────┘       │
                          └──────────────────────────────────────────────────────┘
```

**Data flow:**
- Each department uses a separate API key, showing as a distinct user in metrics
- The MaaS Gateway routes requests to vLLM/llm-d model servers
- Prometheus (via COO) collects per-user token consumption metrics automatically
- MLflow traces every request with token counts, latency, and cost attribution
- Perses dashboards visualize the per-department and per-model breakdown

## Prerequisites

- Red Hat OpenShift AI 3.4+ cluster with vLLM or llm-d deployed
- MaaS Gateway configured with at least one model endpoint
- 3 API keys (one per simulated department) from RHOAI Dashboard > Gen AI Studio
- Cluster Observability Operator (COO) installed for Perses dashboards

## Quick Start

### Option A: Run from your laptop

```bash
# 1. Configure
cp .env.example .env
# Edit .env: set MAAS_GATEWAY, API keys, model names

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify connectivity
./setup-tenants.sh

# 4. Generate traffic (5 minutes by default)
python generate-load.py
```

### Option B: Run on the cluster

```bash
# 1. Configure
cp .env.example .env
# Edit .env: set MAAS_GATEWAY, API keys, MLflow internal URI, namespace

# 2. Deploy as a Kubernetes Job
./deploy-on-cluster.sh
```

### View dashboards

| Dashboard | Location | Shows |
|-----------|----------|-------|
| Perses Usage | OpenShift Console > Observe > Dashboards > Usage | Token consumption by user/model |
| MLflow | OpenShift AI Dashboard > MLflow > "ai-chargeback-demo" | Cost by model, traces per department |

## Load Generators

| Script | Populates Perses | Populates MLflow | Dependencies |
|--------|:---:|:---:|---|
| `generate-load.py` | Yes | Yes | `mlflow`, `openai`, `python-dotenv` |
| `generate-load.sh` | Yes | No | `curl`, `jq` |

Use `generate-load.py` for the full demo. Use `generate-load.sh` if you only need Perses data.

## Traffic Pattern

| Department | Share | Model | Prompt Style | Interval |
|------------|:---:|-------|-------------|:---:|
| Engineering | ~60% | Primary (gemma4) | Long, technical (code review, architecture) | ~5s |
| Marketing | ~25% | Primary (gemma4) | Medium, content generation | ~12s |
| Support | ~15% | Secondary (qwen35-9b) | Short, customer service | ~20s |

## Configuration

All settings are in `.env`. Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAAS_GATEWAY` | -- | Your MaaS Gateway URL (required) |
| `API_KEY_ENGINEERING` | -- | API key for engineering department (required) |
| `API_KEY_MARKETING` | -- | API key for marketing department (required) |
| `API_KEY_SUPPORT` | -- | API key for support department (required) |
| `MAAS_MODEL_PRIMARY` | `gemma4` | Model for engineering + marketing |
| `MAAS_MODEL_SECONDARY` | `qwen35-9b` | Model for support |
| `DURATION_MINUTES` | `5` | How long to run |
| `MLFLOW_TRACKING_URI` | -- | Remote MLflow URL (blank = local SQLite) |

See `.env.example` for the full list.

## Files

```
.
├── .env.example              # Template -- copy to .env and fill in
├── generate-load.py          # Python load generator (Perses + MLflow)
├── generate-load.sh          # Bash load generator (Perses only)
├── setup-tenants.sh          # Validates config and tests connectivity
├── deploy-on-cluster.sh      # Deploys as a K8s Job on OpenShift
├── view-traces.py            # CLI viewer for MLflow traces (no UI needed)
├── Containerfile             # Container image for the load generator
├── requirements.txt          # Python dependencies
├── prompts/
│   ├── engineering.json      # 8 technical prompts
│   ├── marketing.json        # 6 content generation prompts
│   └── support.json          # 5 customer service prompts
├── k8s/
│   ├── configmap-prompts.yaml
│   ├── job-generate-load.yaml
│   ├── rolebinding-mlflow.yaml
│   └── secret-api-keys.yaml  # Template -- replace placeholder values
├── demo-walkthrough.md       # Step-by-step presenter guide
└── chargeback-report-template.md  # Sample board-ready cost report
```

## Demo Walkthrough

See [demo-walkthrough.md](demo-walkthrough.md) for the full presenter guide. Summary:

1. Run `generate-load.py` at least 5 minutes before presenting
2. Open Perses Usage dashboard -- show aggregate tokens across 3 departments
3. Filter by subscription -- isolate one team's usage
4. Filter by model -- show cost split between expensive and cheap models
5. Switch to MLflow -- cost breakdown by model and department
6. Close with the chargeback pitch: real-time cost attribution, no spreadsheets

## Customization

**Prompts:** Edit the JSON files in `prompts/` to match your customer's industry. Each file is an array of `{"role": "user", "content": "..."}` objects.

**Models:** Set `MAAS_MODEL_PRIMARY` and `MAAS_MODEL_SECONDARY` in `.env`. If you only have one model, set both to the same value.

**Duration/intervals:** Adjust `DURATION_MINUTES` and `*_INTERVAL` values in `.env`.
