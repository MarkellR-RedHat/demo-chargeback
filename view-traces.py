#!/usr/bin/env python3
"""
View MLflow traces from the chargeback demo without the MLflow UI.
Works with local SQLite backend.

Usage:
    python view-traces.py              # summary by department
    python view-traces.py --detail     # show individual traces
"""
import argparse
import mlflow

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", action="store_true", help="Show individual traces")
    parser.add_argument("--db", default="sqlite:///mlruns.db", help="MLflow backend URI")
    parser.add_argument("--experiment", default="ai-chargeback-demo")
    args = parser.parse_args()

    mlflow.set_tracking_uri(args.db)
    client = mlflow.MlflowClient()

    exp = client.get_experiment_by_name(args.experiment)
    if not exp:
        print(f"No experiment '{args.experiment}' found.")
        return

    runs = client.search_runs(exp.experiment_id, order_by=["start_time DESC"])
    if not runs:
        print("No runs found.")
        return

    # Aggregate by department
    dept_stats = {}
    for r in runs:
        dept = r.data.tags.get("department", "unknown")
        model = r.data.tags.get("model", "unknown")
        if dept not in dept_stats:
            dept_stats[dept] = {"requests": 0, "model": model}
        dept_stats[dept]["requests"] += 1

    # Try to get trace data for token/cost info
    traces = []
    try:
        trace_list = client.search_traces(experiment_ids=[exp.experiment_id])
        for t in trace_list:
            info = {
                "request_id": t.info.request_id,
                "timestamp": t.info.timestamp_ms,
                "status": t.info.status,
            }
            # Extract attributes from spans
            if t.data and t.data.spans:
                root = t.data.spans[0]
                attrs = root.attributes if hasattr(root, "attributes") else {}
                info["department"] = attrs.get("department", "?")
                info["model"] = attrs.get("model", "?")
                info["total_tokens"] = attrs.get("total_tokens", 0)
                info["cost_usd"] = attrs.get("cost_usd", 0)
                info["latency_ms"] = attrs.get("latency_ms", 0)
                info["status"] = attrs.get("status", "?")
            traces.append(info)
    except Exception:
        traces = []

    print("")
    print("=" * 70)
    print("  AI Chargeback Demo - Trace Summary")
    print("=" * 70)
    print("")
    print(f"  Experiment: {args.experiment}")
    print(f"  Total runs: {len(runs)}")
    print("")

    # Department summary from runs
    print(f"  {'Department':<15} {'Requests':>10} {'Model'}")
    print(f"  {'-'*15:<15} {'-'*10:>10} {'-'*15}")
    for dept in ["engineering", "marketing", "support"]:
        if dept in dept_stats:
            s = dept_stats[dept]
            print(f"  {dept:<15} {s['requests']:>10} {s['model']}")
    print("")

    # If we got trace details, show token/cost summary
    if traces and any(t.get("total_tokens", 0) for t in traces):
        dept_tokens = {}
        for t in traces:
            d = t.get("department", "unknown")
            if d not in dept_tokens:
                dept_tokens[d] = {"tokens": 0, "cost": 0.0, "count": 0}
            dept_tokens[d]["tokens"] += t.get("total_tokens", 0)
            dept_tokens[d]["cost"] += t.get("cost_usd", 0)
            dept_tokens[d]["count"] += 1

        print(f"  {'Department':<15} {'Traces':>8} {'Tokens':>10} {'Est. Cost':>12}")
        print(f"  {'-'*15:<15} {'-'*8:>8} {'-'*10:>10} {'-'*12:>12}")
        total_tok = 0
        total_cost = 0.0
        for dept in ["engineering", "marketing", "support"]:
            if dept in dept_tokens:
                s = dept_tokens[dept]
                print(f"  {dept:<15} {s['count']:>8} {s['tokens']:>10} ${s['cost']:>11.4f}")
                total_tok += s["tokens"]
                total_cost += s["cost"]
        print(f"  {'-'*15:<15} {'-'*8:>8} {'-'*10:>10} {'-'*12:>12}")
        print(f"  {'TOTAL':<15} {len(traces):>8} {total_tok:>10} ${total_cost:>11.4f}")
        print("")

    # Individual traces
    if args.detail and traces:
        print("  Individual traces (most recent first):")
        print("")
        print(f"  {'Time':<12} {'Department':<13} {'Tokens':>8} {'Cost':>10} {'Latency':>10} {'Status'}")
        print(f"  {'-'*12:<12} {'-'*13:<13} {'-'*8:>8} {'-'*10:>10} {'-'*10:>10} {'-'*8}")
        import datetime
        for t in traces[:30]:
            ts = datetime.datetime.fromtimestamp(t.get("timestamp", 0) / 1000).strftime("%H:%M:%S") if t.get("timestamp") else "?"
            dept = t.get("department", "?")
            tokens = t.get("total_tokens", 0)
            cost = t.get("cost_usd", 0)
            latency = t.get("latency_ms", 0)
            status = t.get("status", "?")
            print(f"  {ts:<12} {dept:<13} {tokens:>8} ${cost:>9.4f} {latency:>8}ms {status}")
        if len(traces) > 30:
            print(f"  ... and {len(traces) - 30} more")
        print("")

    print("=" * 70)


if __name__ == "__main__":
    main()
