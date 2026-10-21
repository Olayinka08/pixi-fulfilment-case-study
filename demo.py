"""
demo.py — AI-Assisted Exception Explanation
============================================
Pixi Fulfilment Reconciliation Case Study
Prepared by: Olayinka Bello

Demonstrates one step of the proposed reconciliation pipeline:
  - A reconciliation exception is detected (quantity mismatch)
  - A structured prompt is sent to an LLM
  - The LLM returns a classification, confidence score, and suggested action
  - A low-confidence result triggers the escalation path instead

This demo uses the OpenAI Python SDK (GPT-4o).
To run it you need:
    pip install openai
    export OPENAI_API_KEY="your-key-here"

To test WITHOUT a real API key, run:
    python demo.py --mock

The --mock flag uses a hardcoded response to show the full flow locally.
"""

import json
import sys
import os
import argparse
from datetime import datetime

# ──────────────────────────────────────────────
# 1. SYNTHETIC INPUT: The exception to classify
# ──────────────────────────────────────────────

EXCEPTION = {
    "order_ref": "ORD-4402",
    "sku": "GLOW-50ML",
    "shopify_qty": 2,
    "warehouse_qty": 1,
    "shopify_value": 59.90,
    "order_date": "2024-10-13",
    "warehouse_email": None,  # No email received for this order
}

# Low-confidence scenario (swap this in to trigger the escalation path)
EXCEPTION_LOW_CONF = {
    "order_ref": "ORD-4403",
    "sku": "TONER-100ML",
    "shopify_qty": 5,
    "warehouse_qty": 5,
    "shopify_value": 99.75,
    "order_date": "2024-10-14",
    "warehouse_email": None,
    "_force_low_confidence": True,  # Demo flag only; not part of real pipeline
}

# ──────────────────────────────────────────────
# 2. PROMPT BUILDER
# ──────────────────────────────────────────────

def build_prompt(exception: dict) -> str:
    """
    Builds a structured prompt for the LLM.
    Keeps the instruction explicit so the model returns parseable JSON.
    """
    email_context = (
        f"A warehouse email was received: \"{exception['warehouse_email']}\""
        if exception.get("warehouse_email")
        else "No warehouse email was received for this order."
    )

    prompt = f"""
You are a data analyst assistant helping a beauty brand reconcile weekly fulfilment records.

You have been given a reconciliation exception. Your job is to:
1. Classify the type of exception
2. Provide a confidence score (0.0 to 1.0) for your classification
3. Suggest a specific action for the operations team

Exception details:
- Order reference: {exception['order_ref']}
- SKU: {exception['sku']}
- Quantity in Shopify fulfilment export: {exception['shopify_qty']}
- Quantity in warehouse dispatch file: {exception['warehouse_qty']}
- Order value (Shopify): £{exception['shopify_value']:.2f}
- Order date: {exception['order_date']}
- {email_context}

IMPORTANT RULES:
- You are providing a SUGGESTION only. A human reviewer must approve before any record is updated.
- Never recommend auto-posting to NetSuite. Always end with a human review step.
- If confidence is below 0.70, say so clearly and recommend escalation.

Respond with a JSON object using exactly these keys:
{{
  "exception_type": "<short label>",
  "confidence": <float 0.0-1.0>,
  "explanation": "<one to two sentence explanation>",
  "suggested_action": "<specific action for the ops team>",
  "escalate": <true|false>
}}
""".strip()
    return prompt


# ──────────────────────────────────────────────
# 3. MOCK RESPONSE (no API key needed)
# ──────────────────────────────────────────────

MOCK_RESPONSE_NORMAL = {
    "exception_type": "Partial fulfilment",
    "confidence": 0.72,
    "explanation": (
        "Shopify shows qty=2 but warehouse dispatched only qty=1. "
        "No email context was provided. This is consistent with a partial shipment or back-order."
    ),
    "suggested_action": (
        "Contact warehouse to confirm whether the second unit is back-ordered or held. "
        "Do not post to NetSuite until the remaining quantity is confirmed or written off."
    ),
    "escalate": False,
}

MOCK_RESPONSE_LOW_CONF = {
    "exception_type": "Ambiguous — possible duplicate or data entry error",
    "confidence": 0.48,
    "explanation": (
        "The order ref appears to match but the context is unclear. "
        "Insufficient information to classify with confidence."
    ),
    "suggested_action": (
        "Escalate to the operations manager. Do not post. Request a full transaction log from the warehouse."
    ),
    "escalate": True,
}


# ──────────────────────────────────────────────
# 4. CALL THE LLM (or use mock)
# ──────────────────────────────────────────────

def call_llm(prompt: str, mock: bool = False, force_low: bool = False) -> dict:
    """
    Sends the prompt to GPT-4o and parses the JSON response.
    Falls back to mock data if --mock is passed.
    """
    if mock:
        return MOCK_RESPONSE_LOW_CONF if force_low else MOCK_RESPONSE_NORMAL

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai")
        print("Or use --mock to run without an API key.\n")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        print("Or use --mock to run without an API key.\n")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise data analyst assistant. "
                    "Always respond with valid JSON only. No markdown fences, no extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,  # Low temp: we want consistent, analytical output
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"WARNING: LLM returned non-JSON output:\n{raw}\n")
        return {
            "exception_type": "Parse error",
            "confidence": 0.0,
            "explanation": "LLM response could not be parsed.",
            "suggested_action": "Escalate for manual review.",
            "escalate": True,
        }


# ──────────────────────────────────────────────
# 5. ESCALATION HANDLER
# ──────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.70

def handle_result(exception: dict, result: dict) -> None:
    """
    Decides whether to route the result to human review or immediate escalation.
    Prints a structured audit-ready summary.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    conf = result.get("confidence", 0.0)
    escalate = result.get("escalate", False) or conf < CONFIDENCE_THRESHOLD

    print("\n" + "=" * 60)
    print("RECONCILIATION EXCEPTION REPORT")
    print("=" * 60)
    print(f"  Order ref    : {exception['order_ref']}")
    print(f"  SKU          : {exception['sku']}")
    print(f"  Shopify qty  : {exception['shopify_qty']}")
    print(f"  Warehouse qty: {exception['warehouse_qty']}")
    print(f"  Order date   : {exception['order_date']}")
    print("-" * 60)
    print("AI SUGGESTION (not a confirmed resolution)")
    print("-" * 60)
    print(f"  Exception type   : {result.get('exception_type', 'Unknown')}")
    print(f"  Confidence score : {conf:.2f}  (threshold: {CONFIDENCE_THRESHOLD})")
    print(f"  Explanation      : {result.get('explanation', '')}")
    print(f"  Suggested action : {result.get('suggested_action', '')}")
    print("-" * 60)

    if escalate:
        print("  ROUTING  →  ESCALATE to Ops Manager")
        print("  REASON   →  Confidence below threshold or explicit escalation flag")
        print("  STATUS   →  Exception held. No posting to NetSuite.")
    else:
        print("  ROUTING  →  HUMAN REVIEW QUEUE")
        print("  STATUS   →  Awaiting approval from named reviewer before any action")
        print("  GUARDRAIL:  This suggestion does NOT auto-resolve the exception.")
        print("              A human must approve before NetSuite posting.")

    print("-" * 60)
    print(f"  Logged at    : {timestamp}")
    print(f"  AI model     : gpt-4o (or mock)")
    print("=" * 60 + "\n")


# ──────────────────────────────────────────────
# 6. MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pixi fulfilment reconciliation — AI exception explanation demo"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use hardcoded mock response instead of calling the OpenAI API",
    )
    parser.add_argument(
        "--scenario",
        choices=["normal", "escalation"],
        default="normal",
        help="'normal' = partial shipment (confidence 0.72); 'escalation' = low-confidence escalation path",
    )
    args = parser.parse_args()

    # Pick scenario
    exception = EXCEPTION_LOW_CONF if args.scenario == "escalation" else EXCEPTION
    force_low = args.scenario == "escalation"

    print("\nPixi Fulfilment Reconciliation — AI Exception Demo")
    print(f"Scenario : {args.scenario}")
    print(f"Mode     : {'MOCK (no API call)' if args.mock else 'LIVE (OpenAI API)'}\n")

    # Build prompt
    prompt = build_prompt(exception)
    print("── PROMPT SENT TO LLM ──────────────────────────────")
    print(prompt)
    print("────────────────────────────────────────────────────\n")

    # Call LLM
    result = call_llm(prompt, mock=args.mock, force_low=force_low)

    # Handle result
    handle_result(exception, result)


if __name__ == "__main__":
    main()
