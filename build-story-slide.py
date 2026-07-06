"""
Persona 3: Finance / Business Leader - Visual storytelling slide.
Shows the chargeback flow with data from actual screenshots.
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/presentation-assets"))
from rh_deck_generator import RedHatDeck, Color

deck = RedHatDeck()

# Slide 1: The story flow
deck.add_title_slide(
    title="AI Chargeback\nin 60 Seconds",
    subtitle="How the VP of Finance answers: what did AI cost us, by department?",
    presenter="Persona 3: Finance / Business Leader",
    presenter_title="RHOAI Observability Demo",
    notes=(
        "This slide tells the chargeback story for the Finance persona. "
        "The CFO walks in and asks: what did AI cost us this quarter, by department? "
        "We answer that question using two tools that are already collecting data: "
        "the Perses Usage dashboard for platform-level token consumption, and "
        "MLflow for per-department application-level traces and token breakdown."
    ),
)

# Slide 2: The Platform View (Perses)
deck.add_accent_cards_slide(
    title="Platform view: who consumed what",
    subtitle="Perses Usage Dashboard -- 837K tokens across 2K requests in 24 hours",
    section_label="STEP 1: PERSES",
    cards=[
        {"label": "837K total tokens",
         "body": "2,000 requests. 100% success rate. Three distinct consumption streams "
                 "visible by subscription and model. Zero setup required.",
         "accent_color": Color.RED},
        {"label": "gemma4 on primary subscription",
         "body": "538K tokens across 1,000 requests. This is Engineering: heavy code review, "
                 "architecture prompts, long responses. 64% of total platform consumption.",
         "accent_color": Color.TEAL},
        {"label": "gemma4 on secondary subscription",
         "body": "185K tokens across 565 requests. Marketing: content generation, blog drafts, "
                 "campaign copy. 22% of platform consumption.",
         "accent_color": Color.BLUE},
        {"label": "qwen35-9b on primary subscription",
         "body": "114K tokens across 419 requests. Support: short ticket responses on a smaller, "
                 "cheaper model. 14% of consumption. Good cost discipline.",
         "accent_color": Color.DEEP_RED},
    ],
    notes=(
        "Open the Perses Usage dashboard. The overview shows 837K tokens across 2K requests "
        "in the last 24 hours. The Token Consumption table breaks it down by subscription and model. "
        "Three rows. Engineering drove 64% of tokens on the expensive model. Marketing drove 22%. "
        "Support drove 14% on the cheaper model. This is the data the finance team needs for chargeback. "
        "No spreadsheets. No exports. It's already here."
    ),
)

# Slide 3: The Department View (MLflow)
deck.add_card_grid_slide(
    title="Department view: token consumption per team",
    subtitle="Three MLflow experiments -- one per department. Each has its own usage dashboard.",
    section_label="STEP 2: MLFLOW",
    columns=3,
    cards=[
        {"label": "Engineering",
         "body": "305 traces. 61.3K tokens (7K in, 54K out). "
                 "573 avg tokens/trace. Heaviest consumer.",
         "accent_color": Color.RED},
        {"label": "Marketing",
         "body": "169 traces. 27.7K tokens (4.4K in, 23.2K out). "
                 "374 avg tokens/trace. Moderate usage.",
         "accent_color": Color.TEAL},
        {"label": "Support",
         "body": "109 traces. 14.5K tokens (2.5K in, 12K out). "
                 "322 avg tokens/trace. Lightest consumer.",
         "accent_color": Color.BLUE},
    ],
    notes=(
        "Switch to MLflow. Three experiments: ai-chargeback-demo-engineering, marketing, support. "
        "Click into Engineering. 305 traces, 61K tokens, 573 avg per trace. Engineering's prompts are "
        "long (code review, architecture) so token consumption is high. "
        "Click into Support. 109 traces, 14.5K tokens, 322 avg per trace. Short ticket responses. "
        "The per-department split makes the cost attribution story obvious: Engineering consumes 4x "
        "what Support does. That's what finance needs to hear."
    ),
)

# Slide 4: The Audit Trail
deck.add_accent_cards_slide(
    title="Audit trail: every request is traceable",
    subtitle="305 engineering traces with full request, response, and execution time",
    section_label="STEP 3: TRACES",
    cards=[
        {"label": "Per-request visibility",
         "body": "Every inference call logged with trace ID, prompt, response, token count, "
                 "execution time, and status. The audit trail regulators ask for.",
         "accent_color": Color.RED},
        {"label": "Prompt content visible",
         "body": "\"Review this Python function for security vulnerabilities\" -- "
                 "\"Design a REST API schema for a model serving registry\" -- "
                 "real engineering prompts, not synthetic test data.",
         "accent_color": Color.TEAL},
        {"label": "5-6 second execution times",
         "body": "Engineering traces average 5.5s. That's the SLA baseline. "
                 "If latency spikes, the trace log shows exactly when and which requests.",
         "accent_color": Color.BLUE},
    ],
    notes=(
        "Click Traces in the engineering experiment. 305 traces with full audit trail. "
        "Each row shows the trace ID, the actual prompt sent, the response received, "
        "execution time, and status. Click into any trace and you see the full span detail. "
        "This is what regulators ask for in telco and financial services: "
        "what did the model process, when, and what did it return? "
        "For the demo, point to a specific trace: 'This request asked for a security code review, "
        "consumed 589 tokens, took 5.7 seconds, and returned a detailed vulnerability analysis. "
        "Every request is traceable.'"
    ),
)

# Slide 5: The Punchline
deck.add_stat_slide(
    title="The CFO's answer in four numbers",
    subtitle="What did AI cost us this quarter, by department?",
    section_label="THE ANSWER",
    stats=[
        {"number": "837K", "label": "Total tokens consumed across all departments"},
        {"number": "64%", "label": "Engineering (heaviest: code review, architecture)"},
        {"number": "22%", "label": "Marketing (moderate: content, campaigns)"},
        {"number": "14%", "label": "Support (lightest: short responses, cheap model)"},
    ],
    notes=(
        "Close with the four numbers that answer the CFO's question. "
        "837K total tokens. Engineering took 64% on the expensive model. "
        "Marketing took 22%. Support took 14% on the cheap model. "
        "Today this data is in dashboards. In the next release, a metering webhook "
        "pushes these same token events directly to your billing system in real time. "
        "Per-request, per-model, per-user. No dashboards required."
    ),
)

out = "demo-chargeback-story.pptx"
deck.save(out)
print(f"Done. {len(deck.prs.slides)} slides saved to {out}")
