# AI Chargeback in 60 Seconds -- Presenter Walkthrough

**Persona:** Finance / Business Leader (VP Finance, FinOps Lead, CFO)
**Runtime:** 5-7 minutes
**Pre-requisite:** Run `./generate-load.sh` at least 5 minutes before the demo

---

## Before you start

1. Run `./generate-load.sh` and let it run for 5 minutes. You can leave it running during the demo.
2. Have two browser tabs ready:
   - Perses dashboards: OpenShift Console > Observe > Dashboards
   - MLflow UI: OpenShift AI Dashboard > MLflow

---

## The Opening (30 seconds)

**Say this:**

> "The CFO walks into your office and asks: what did AI cost us this quarter, by department? Today I'm going to answer that question in under 60 seconds using data that's already being collected. No spreadsheets. No exports. No separate billing platform."

---

## Step 1: Perses Usage Dashboard (60 seconds)

**Navigate to:** Perses > Usage Overview dashboard

**What you'll see:**
- Total tokens consumed across all departments
- Total requests served
- Number of active users/API keys

**Talk track:**
> "This is our Usage dashboard. It shows everything that happened on this AI platform. Total tokens consumed, total requests, broken down by who's using it. No one had to set this up. It collects automatically when you deploy a model."

**Click into the per-user breakdown table.**

**Talk track:**
> "Here's where it gets interesting for finance. Three departments are using this platform: engineering, marketing, and support. Engineering consumed about 60% of the tokens. Marketing about 25%. Support about 15%. The API key tells us exactly who is who."

**Pause. Let the numbers land.**

---

## Step 2: Filter by Subscription and Model (45 seconds)

**Use the Subscription dropdown to filter to one subscription.**

**Talk track:**
> "I can filter by subscription to isolate one team's usage. This subscription drove 35K tokens across 55 requests on the premium model. That's your heavy consumer."

**Clear the filter. Now use the Model dropdown to filter by model.**

**Talk track:**
> "Now filter by model. gemma4 consumed 51K tokens. qwen35-9b consumed 7K. The cost per token is different for each model, so this split matters for chargeback. Your heavy workloads are on the expensive model. Your lightweight workloads are on the cheap one. That's exactly the kind of cost discipline finance wants to see."

---

## Step 3: MLflow Cost Breakdown (45 seconds)

**Switch to MLflow UI > Experiment > Overview > scroll to Cost Breakdown.**

**Talk track:**
> "Now let's look at it from the application side. MLflow tracks cost by model. You can see granite-3b is handling about 70% of the spend. The smaller model used by support is much cheaper per token. This is the per-model attribution that finance needs for chargeback."

**Point to the Cost Over Time chart.**

**Talk track:**
> "Cost over time shows the trend. If a department's spend spikes on a Tuesday, you see it here. No waiting for monthly invoices. No CSV exports. Real-time."

---

## Step 4: The Token Usage Detail (30 seconds)

**Scroll to Token Usage panel.**

**Talk track:**
> "Input tokens versus output tokens matters for pricing. Engineering's prompts are long (high input), and they ask for detailed responses (high output). Support has short prompts and short responses. The cost per request is very different between departments. This is the granularity your FinOps team needs."

---

## Step 5: The Chargeback Pitch (30 seconds)

**Talk track:**
> "So to answer the CFO's question: engineering consumed 60% of tokens on the expensive model, marketing consumed 25% but is underutilizing their GPU allocation, and support consumed 15% on a cheaper model. Total platform cost, broken down by department, by model, by user, available right now."

> "Today this is in dashboards. In the next release, a metering webhook pushes this same data directly to your billing system in real time. Per-request token events, machine to machine. No dashboards required."

---

## Closing (15 seconds)

**Talk track:**
> "Observability isn't just about keeping the lights on. It's about knowing what you're spending, who's spending it, and whether it's worth it. The data is already here. You just need to look at it."

---

## If they ask about chargeback automation

> "The metering webhook in 3.5 Dev Preview emits a structured event for every inference request: user, model, input tokens, output tokens, latency, request ID. Your BSS or billing system subscribes to that stream and generates invoices. We're working with several telco and financial services customers on exactly this flow right now."

## If they ask about cost per request

> "MLflow already shows cost per model with provider-level pricing. For infrastructure-level cost-per-request (factoring in GPU time, not just token pricing), that requires correlating token data with GPU utilization data. That's on the roadmap for 3.6 with per-model metrics at the platform level."

## If they ask about multi-cluster

> "Each cluster has its own Prometheus and MLflow instance. Cross-cluster cost aggregation is a roadmap item. Today, each cluster reports independently. For organizations running multiple clusters, the OTel export path lets you send all metrics to a central Grafana or Datadog instance for unified cost views."
