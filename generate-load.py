#!/usr/bin/env python3
"""
AI Chargeback Demo - Multi-tenant load generator with MLflow tracing.

Sends inference requests as 3 departments (engineering, marketing, support)
and logs every request as an MLflow trace with token usage and cost data.

Requirements:
    pip install mlflow openai python-dotenv

Usage:
    python generate-load.py              # 5 minutes, default settings
    python generate-load.py --duration 2 # 2 minutes
    python generate-load.py --dry-run    # print config, don't send requests
"""
import os
import sys
import json
import time
import random
import signal
import argparse
import threading
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env from script directory
SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

GATEWAY = os.environ.get("MAAS_GATEWAY", "")
MODEL_PRIMARY = os.environ.get("MAAS_MODEL_PRIMARY", "gemma4")
MODEL_SECONDARY = os.environ.get("MAAS_MODEL_SECONDARY", MODEL_PRIMARY)

# Per-model cost assumptions ($ per 1K tokens) for MLflow cost tracking
# Adjust these to match your actual provider pricing
COST_PER_1K = {
    MODEL_PRIMARY: {"input": 0.015, "output": 0.045},
    MODEL_SECONDARY: {"input": 0.005, "output": 0.015},
}

ALIAS_PRIMARY = os.environ.get("MLFLOW_MODEL_ALIAS_PRIMARY", MODEL_PRIMARY)
ALIAS_SECONDARY = os.environ.get("MLFLOW_MODEL_ALIAS_SECONDARY", MODEL_SECONDARY)

TENANTS = {
    "engineering": {
        "api_key": os.environ.get("API_KEY_ENGINEERING", ""),
        "model": MODEL_PRIMARY,
        "model_alias": ALIAS_PRIMARY,
        "max_tokens": int(os.environ.get("MAX_TOKENS_ENGINEERING", "512")),
        "interval": int(os.environ.get("ENGINEERING_INTERVAL", "5")),
        "prompts_file": SCRIPT_DIR / "prompts" / "engineering.json",
    },
    "marketing": {
        "api_key": os.environ.get("API_KEY_MARKETING", ""),
        "model": MODEL_PRIMARY,
        "model_alias": ALIAS_PRIMARY,
        "max_tokens": int(os.environ.get("MAX_TOKENS_MARKETING", "384")),
        "interval": int(os.environ.get("MARKETING_INTERVAL", "12")),
        "prompts_file": SCRIPT_DIR / "prompts" / "marketing.json",
    },
    "support": {
        "api_key": os.environ.get("API_KEY_SUPPORT", ""),
        "model": MODEL_SECONDARY,
        "model_alias": ALIAS_SECONDARY,
        "max_tokens": int(os.environ.get("MAX_TOKENS_SUPPORT", "256")),
        "interval": int(os.environ.get("SUPPORT_INTERVAL", "20")),
        "prompts_file": SCRIPT_DIR / "prompts" / "support.json",
    },
}


@dataclass
class TenantStats:
    requests: int = 0
    tokens: int = 0
    cost: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


def load_prompts(path):
    with open(path) as f:
        return json.load(f)


def calculate_cost(model, input_tokens, output_tokens):
    rates = COST_PER_1K.get(model, {"input": 0.01, "output": 0.03})
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])


def send_request(tenant_name, config, prompts, stats, mlflow_experiment):
    """Send inference request with two-span structure matching MLflow demo pattern."""
    import mlflow
    from openai import OpenAI

    prompt = random.choice(prompts)
    content = prompt["content"]
    model = config["model"]
    model_alias = config.get("model_alias", model)
    rates = COST_PER_1K.get(model, {"input": 0.01, "output": 0.03})

    client = OpenAI(
        base_url=f"{GATEWAY}/prelude-maas/{model}/v1",
        api_key=config["api_key"],
    )

    messages = [
        {"role": "system", "content": "You are a helpful AI assistant working for a large enterprise."},
        {"role": "user", "content": content},
    ]

    start = time.time()
    try:
        # Parent span (like chat_agent in the demo)
        with mlflow.start_span(name=f"{tenant_name}_agent", span_type="AGENT") as parent:
            parent.set_inputs({"message": content[:200], "department": tenant_name})

            # Child span (like generate_response in the demo)
            with mlflow.start_span(name="generate_response", span_type="CHAT_MODEL") as child:
                child.set_inputs({"messages": messages, "model": model_alias})

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=config["max_tokens"],
                    stream=False,
                )

                latency = time.time() - start
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0
                total_tokens = response.usage.total_tokens if response.usage else 0
                input_cost = input_tokens / 1000 * rates["input"]
                output_cost = output_tokens / 1000 * rates["output"]
                total_cost = input_cost + output_cost
                answer = response.choices[0].message.content if response.choices else ""

                child.set_outputs({
                    "choices": [{"message": {"role": "assistant", "content": answer[:300]}}],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    },
                    "model": model_alias,
                    "id": f"chatcmpl-{tenant_name}-{int(time.time())}",
                    "object": "chat.completion",
                })

            parent.set_outputs({"response": answer[:200]})

        with stats.lock:
            stats.requests += 1
            stats.tokens += total_tokens
            stats.cost += total_cost

        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {tenant_name:<13}  {total_tokens:>5} tokens  ${total_cost:.4f}  ({model} -> {model_alias})")

    except Exception as e:
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {tenant_name:<13}  ERROR: {str(e)[:60]}")


def run_tenant(tenant_name, config, duration_seconds, stats, experiment_name, stop_event, split_experiments=False):
    """Run load for one tenant until duration expires or stop is signaled."""
    import mlflow

    prompts = load_prompts(config["prompts_file"])

    if split_experiments:
        dept_experiment = f"{experiment_name}-{tenant_name}"
        try:
            mlflow.set_experiment(dept_experiment)
        except Exception:
            pass

    end_time = time.time() + duration_seconds
    while time.time() < end_time and not stop_event.is_set():
        try:
            with mlflow.start_run(run_name=f"{tenant_name}-{int(time.time())}",
                                  experiment_id=mlflow.get_experiment_by_name(
                                      f"{experiment_name}-{tenant_name}" if split_experiments else experiment_name
                                  ).experiment_id if split_experiments else None):
                mlflow.set_tag("department", tenant_name)
                mlflow.set_tag("model", config["model"])
                send_request(tenant_name, config, prompts, stats, experiment_name)
        except Exception:
            send_request(tenant_name, config, prompts, stats, experiment_name)

        jitter = random.randint(config["interval"] // 2, config["interval"] + config["interval"] // 2)
        stop_event.wait(jitter)


def print_summary(all_stats):
    print("")
    print("")
    print("=" * 64)
    print("  Load Generation Summary")
    print("=" * 64)
    print("")
    print(f"  {'Department':<15} {'Requests':>8} {'Tokens':>10} {'Est. Cost':>10} {'Model'}")
    print(f"  {'-'*15:<15} {'-'*8:>8} {'-'*10:>10} {'-'*10:>10} {'-'*10}")
    total_req = 0
    total_tok = 0
    total_cost = 0.0
    for name in ["engineering", "marketing", "support"]:
        s = all_stats[name]
        model = TENANTS[name]["model"]
        print(f"  {name:<15} {s.requests:>8} {s.tokens:>10} ${s.cost:>9.4f} {model}")
        total_req += s.requests
        total_tok += s.tokens
        total_cost += s.cost
    print(f"  {'-'*15:<15} {'-'*8:>8} {'-'*10:>10} {'-'*10:>10}")
    print(f"  {'TOTAL':<15} {total_req:>8} {total_tok:>10} ${total_cost:>9.4f}")
    print("")
    print("  Dashboards should now show per-tenant breakdown.")
    print("  Perses > Usage for token consumption.")
    print("  MLflow > Experiment for cost and traces.")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(description="AI Chargeback Demo - Load Generator")
    parser.add_argument("--duration", type=int, default=int(os.environ.get("DURATION_MINUTES", "5")),
                        help="Duration in minutes (default: 5)")
    parser.add_argument("--experiment", type=str, default="ai-chargeback-demo",
                        help="MLflow experiment name prefix")
    parser.add_argument("--split-experiments", action="store_true",
                        help="Create separate MLflow experiment per department")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    args = parser.parse_args()

    if not GATEWAY:
        print("ERROR: MAAS_GATEWAY not set. Edit .env first.")
        sys.exit(1)

    print("=" * 64)
    print("  AI Chargeback Demo - Load Generator (with MLflow tracing)")
    print("=" * 64)
    print("")
    print(f"  Gateway:      {GATEWAY}")
    print(f"  Duration:     {args.duration} minutes")
    print(f"  Experiment:   {args.experiment}")
    print("")
    for name, cfg in TENANTS.items():
        rates = COST_PER_1K.get(cfg["model"], {})
        alias_info = f"  (MLflow: {cfg['model_alias']})" if cfg.get('model_alias') != cfg['model'] else ""
        print(f"  {name:<13}  model={cfg['model']}{alias_info}  interval={cfg['interval']}s  "
              f"max_tokens={cfg['max_tokens']}  "
              f"${rates.get('input', '?')}/{rates.get('output', '?')} per 1K tok")
    print("")

    if args.dry_run:
        print("  (dry-run mode, exiting)")
        return

    # Import mlflow here so --dry-run works without it installed
    try:
        import mlflow
    except ImportError:
        print("ERROR: mlflow not installed. Run: pip install mlflow openai python-dotenv")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai not installed. Run: pip install mlflow openai python-dotenv")
        sys.exit(1)

    # Configure MLflow
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    tracking_token = os.environ.get("MLFLOW_TRACKING_TOKEN", "")
    token_file = os.environ.get("MLFLOW_TRACKING_TOKEN_FILE", "")
    workspace = os.environ.get("MLFLOW_WORKSPACE", "")

    # Read token from file if running in-cluster (K8s service account)
    if not tracking_token and token_file and os.path.isfile(token_file):
        with open(token_file) as f:
            tracking_token = f.read().strip()
        print(f"  MLflow auth:  token from {token_file}")

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
        print(f"  MLflow URI:   {tracking_uri}")
    else:
        print("  MLflow URI:   local (set MLFLOW_TRACKING_URI for remote)")

    if tracking_token:
        os.environ["MLFLOW_TRACKING_TOKEN"] = tracking_token
        os.environ["MLFLOW_HTTP_REQUEST_HEADERS"] = json.dumps({
            "Authorization": f"Bearer {tracking_token}"
        })
        print(f"  MLflow auth:  token set ({tracking_token[:12]}...)")
    else:
        print("  MLflow auth:  none (set MLFLOW_TRACKING_TOKEN for remote)")

    experiment_name = args.experiment
    if workspace:
        print(f"  MLflow workspace: {workspace}")
    print(f"  Experiment:   {experiment_name}")
    print("")

    mlflow_ready = False

    if tracking_uri and workspace:
        try:
            mlflow.set_workspace(workspace)
            client = mlflow.MlflowClient()
            exps = client.search_experiments(
                filter_string=f"name = '{experiment_name}'"
            )
            if exps:
                mlflow_experiment_id = exps[0].experiment_id
            else:
                mlflow_experiment_id = client.create_experiment(experiment_name)
            import mlflow.tracking.fluent as _fluent
            _fluent._active_experiment_id = mlflow_experiment_id
            print(f"  [OK] Remote experiment ready (id={mlflow_experiment_id})")
            mlflow_ready = True
        except Exception as e:
            print(f"  [WARN] Remote MLflow with workspace failed: {e}")

    elif tracking_uri:
        try:
            mlflow.set_experiment(experiment_name)
            print(f"  [OK] Remote experiment ready")
            mlflow_ready = True
        except Exception as e:
            print(f"  [WARN] Remote MLflow failed: {e}")

    if not mlflow_ready:
        try:
            print("  Falling back to local SQLite tracking...")
            os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
            mlflow.set_tracking_uri("sqlite:///mlruns.db")
            mlflow.set_experiment(experiment_name)
            print(f"  [OK] Local experiment created. View with: mlflow ui --backend-store-uri sqlite:///mlruns.db")
            mlflow_ready = True
        except Exception as e:
            print(f"  [WARN] Local MLflow also failed: {e}")
            print(f"  Continuing without MLflow tracing. Perses will still get data.")

    # Disable autolog - we set token/cost attributes manually
    mlflow.autolog(disable=True)

    print("  Press Ctrl+C to stop early and see summary.")
    print("")
    print("  Live requests:")
    print("")

    all_stats = {name: TenantStats() for name in TENANTS}
    stop_event = threading.Event()
    duration_seconds = args.duration * 60

    def handle_signal(sig, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.split_experiments:
        print("  Mode: separate experiment per department")
        print(f"    {args.experiment}-engineering")
        print(f"    {args.experiment}-marketing")
        print(f"    {args.experiment}-support")
        print("")

    threads = []
    for name, config in TENANTS.items():
        t = threading.Thread(
            target=run_tenant,
            args=(name, config, duration_seconds, all_stats[name], args.experiment,
                  stop_event, args.split_experiments),
            daemon=True,
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print_summary(all_stats)


if __name__ == "__main__":
    main()
