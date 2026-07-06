# AI Platform Cost Report
**Period:** Q3 2026 (July - September)
**Prepared for:** VP Finance / FinOps Review
**Source:** Red Hat OpenShift AI Observability (Perses + MLflow)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total inference requests | 79,420 |
| Total tokens consumed | 634M |
| Active users / API keys | 11 |
| GPU nodes allocated | 4 |
| Average GPU utilization | 68% |
| Estimated total cost | $14,200 |

---

## Cost by Department

| Department | Requests | Tokens | % of Total | Primary Model | Est. Cost | GPU Util |
|------------|----------|--------|------------|---------------|-----------|----------|
| Engineering | 47,650 | 380M | 60% | granite-3b | $9,120 | 78% |
| Marketing | 19,855 | 159M | 25% | granite-3b | $3,550 | 32% |
| Support | 11,915 | 95M | 15% | qwen-0.5b | $1,530 | 45% |

---

## Cost by Model

| Model | Requests | Tokens | Cost / 1K tokens | Est. Cost | % of Spend |
|-------|----------|--------|-------------------|-----------|------------|
| granite-3b-instruct | 67,505 | 539M | $0.012 | $6,468 | 64% |
| qwen-0.5b-instruct | 11,915 | 95M | $0.004 | $380 | 4% |

*Note: Cost estimates based on provider pricing. Actual infrastructure cost (GPU hours) calculated separately.*

---

## Observations

**Engineering (60% of spend)**
- Justified. GPU utilization at 78% indicates efficient use.
- Long prompts (code review, architecture) drive high token consumption.
- Recommendation: maintain current allocation.

**Marketing (25% of spend, 32% GPU utilization)**
- GPU allocation is oversized. 32% utilization means 68% of allocated GPU capacity is idle.
- At $50K/node/year, approximately $34K in idle capacity annually.
- Recommendation: right-size GPU allocation or consolidate with engineering's pool.

**Support (15% of spend)**
- Using the smaller, cheaper model. Good cost discipline.
- GPU utilization at 45% is reasonable for burst workloads.
- Recommendation: no changes needed.

---

## Trend: Cost Over Time (Monthly)

| Month | Engineering | Marketing | Support | Total |
|-------|------------|-----------|---------|-------|
| July | $3,040 | $1,180 | $510 | $4,730 |
| August | $3,200 | $1,250 | $520 | $4,970 |
| September | $2,880 | $1,120 | $500 | $4,500 |

*Engineering cost decreased in September due to a model quantization optimization that reduced tokens per request by 15%.*

---

## Action Items

1. **Marketing GPU right-sizing** -- Schedule review with marketing platform lead. Target: reduce allocation by 1 GPU node ($50K annual savings).
2. **Engineering model optimization** -- The quantization improvement in September shows 15% token reduction. Evaluate extending this to all engineering workloads.
3. **Automated chargeback pipeline** -- RHOAI 3.5 introduces a metering webhook that pushes per-request token events to BSS. Schedule integration with the billing team.

---

*Report generated from Perses Usage Dashboard and MLflow Cost Breakdown panels.*
*Data sources: Prometheus/Thanos (platform metrics), MLflow (application metrics).*
*For questions, contact the AI Platform team.*
