# Pixi — AI-Assisted Fulfilment Reconciliation

**Case study submission by Olayinka Bello**

A worked proposal for replacing Pixi's manual weekly fulfilment reconciliation with an AI-assisted pipeline — reducing human review time from ~4 hours to ~1 hour per week while keeping every decision traceable and under human control.

## Live Demo

View the interactive brief at: `https://[your-username].github.io/pixi-fulfilment-case-study/`

## Contents

| File | Description |
|---|---|
| `index.html` | Two-page interactive visual brief: workflow, architecture, AI judgment framework, business outcomes and pilot plan |
| `worked-example.html` | Synthetic worked example: four reconciliation scenarios with source data, reconciliation output table and scenario detail cards |
| `demo.py` | Runnable Python script demonstrating the AI exception explanation step |

## Running the Python Demo

```bash
# No API key needed — uses mock response
python demo.py --mock

# Trigger the escalation path (low-confidence scenario)
python demo.py --mock --scenario escalation

# Live mode (requires OpenAI API key)
pip install openai
export OPENAI_API_KEY="your-key-here"
python demo.py --scenario normal
```

## Architecture Summary

```
Shopify Fulfilment API
Warehouse Dispatch CSV      →  Bronze (raw)  →  Silver (match)  →  AI triage  →  Human review  →  NetSuite export
Warehouse Email (IMAP)
```

Key design decisions:
- Deterministic rules handle clean matches — AI is never called for clear cases
- LLM API (GPT-4o or Claude) classifies exceptions and parses warehouse emails
- Confidence threshold of 0.70: below this, the exception is auto-escalated
- No auto-posting to NetSuite — human sign-off required on every export
- Full audit trail: AI suggestion and human decision stored separately

## Enabling GitHub Pages

1. Go to **Settings → Pages** in this repository
2. Under **Source**, select **Deploy from a branch**
3. Select **main** branch, **/ (root)** folder
4. Click **Save** — the site will be live within a minute

---

*Prepared by Olayinka Bello · linkedin.com/in/olayinka-bello-mba-04960b12a*
