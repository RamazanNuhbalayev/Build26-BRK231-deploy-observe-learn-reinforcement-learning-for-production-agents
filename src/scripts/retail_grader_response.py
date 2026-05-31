"""Response-only grader for the Retail Post-Purchase Resolution Desk agent.

Scores agent output based solely on the final response text (no tool-call traces required).
Designed for use with hosted agent endpoints that only return the final message.

Scoring dimensions:
  1. Decision Correctness (50%) - right action + item identification
  2. Financial Accuracy (30%)  - dollar amounts match expected
  3. Format Compliance (20%)   - adheres to MANDATORY response format

Expected response format:
  Action: <action> for <item_id> (reason: <reason>). Amount: $<amount>.
  Action: deny for <item_id> (reason: <denial_reason>).
"""

import json
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Regex patterns (inline to avoid compile() restrictions in sandboxed environments)
# PRIMARY pattern: Action: refund for LI-013 (reason: changed_mind). Amount: $79.99.
_ACTION_PATTERN_STR = r"Action:\s*(\w+)\s+for\s+([\w-]+)\s*\(reason:\s*([^)]+)\)"
_AMOUNT_PATTERN_STR = r"Amount:\s*\$?([\d,]+\.?\d*)"

# FLEXIBLE patterns for common variations
_FLEXIBLE_PATTERNS = [
    # Pattern 1: Action: <action> for <item> (reason: <reason>)
    r"Action:\s*(\w+)\s+for\s+([\w-]+)\s*\(reason:\s*([^)]+)\)",
    # Pattern 2: Action: <action> <item> (reason <reason>)  - missing "for", optional colon
    r"Action:\s*(\w+)\s+([\w-]+)\s*\(?reason:?\s*([^)]+)\)?",
    # Pattern 3: <action> for <item>... reason: <reason>
    r"(\w+)\s+for\s+(?:item\s+)?([\w-]+).*?reason:?\s*([^\.,\n]+)",
    # Pattern 4: Process <action>... <item>... <reason>
    r"(?:process|approved?|submit)\s+(\w+)\s+for.*?([\w-]+).*?(?:due to|because|reason):\s*([^\.,\n]+)",
]


def parse_action_lines(response: str) -> list[dict]:
    """
    Extract structured action lines from agent response text.
    Uses multiple patterns to handle format variations.
    """
    results = []
    lines = response.split("\n")
    
    # Try to parse the full response as well (not just line-by-line)
    all_text = [response]  # Parse full response
    all_text.extend(lines)  # Also try line-by-line

    seen_items = set()  # Avoid duplicates
    
    for text in all_text:
        # Try each pattern in order
        for pattern in _FLEXIBLE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    action = match.group(1).lower().strip()
                    item_id = match.group(2).strip()
                    reason = match.group(3).strip().rstrip(".,")
                    
                    # Skip if we've already seen this item (avoid duplicates)
                    if item_id in seen_items:
                        continue
                    
                    # Validate action is a known type
                    valid_actions = {
                        'refund', 'exchange', 'replacement', 'store_credit', 
                        'shipping_credit', 'cancel', 'deny', 'return'
                    }
                    if action not in valid_actions:
                        continue
                    
                    # Normalize "return" to "refund"
                    if action == 'return':
                        action = 'refund'
                    
                    entry = {
                        "action": action,
                        "item_id": item_id,
                        "reason": reason,
                    }
                    
                    # Look for amount in the same text
                    amount_match = re.search(_AMOUNT_PATTERN_STR, text, re.IGNORECASE)
                    if amount_match:
                        entry["amount"] = float(amount_match.group(1).replace(",", ""))
                    else:
                        entry["amount"] = None
                    
                    results.append(entry)
                    seen_items.add(item_id)
                    
                except (IndexError, ValueError):
                    continue
    
    return results


# ---------------------------------------------------------------------------
# 1. Decision Correctness (50%)
# ---------------------------------------------------------------------------

def score_decision(response: str, scenario: dict) -> dict:
    """Score whether the agent picked the correct action for each item."""
    expected_actions = scenario.get("expected_actions", {})
    if not expected_actions:
        return {"score": 1.0, "details": "No expected actions (pass-through)"}

    parsed = parse_action_lines(response)

    # Group by item_id (an item can have multiple action lines, e.g., deny + shipping_credit)
    parsed_by_item: dict[str, list[dict]] = {}
    for p in parsed:
        parsed_by_item.setdefault(p["item_id"], []).append(p)

    item_scores = {}
    for item_id, expected in expected_actions.items():
        exp_action = expected["action"].lower()

        if item_id not in parsed_by_item:
            item_scores[item_id] = _fallback_decision_score(response, exp_action, item_id)
            continue

        # Check if ANY action line for this item matches the expected action
        actions_for_item = parsed_by_item[item_id]
        best_score = 0.0
        best_match = "not_found"

        for actual in actions_for_item:
            act_action = actual["action"]
            if act_action == exp_action:
                best_score = 1.0
                best_match = "exact"
                break
            elif _actions_compatible(exp_action, act_action):
                if 0.7 > best_score:
                    best_score = 0.7
                    best_match = "compatible"

        if best_score == 0.0:
            got = [a["action"] for a in actions_for_item]
            best_match = f"mismatch: expected={exp_action}, got={got}"

        item_scores[item_id] = {"score": best_score, "match": best_match}

    total = len(item_scores)
    avg = sum(v["score"] for v in item_scores.values()) / total if total else 1.0

    return {"score": avg, "per_item": item_scores}


def _actions_compatible(expected: str, actual: str) -> bool:
    """Check if actions are in the same family (partial credit)."""
    resolution_family = {"refund", "replacement", "store_credit", "exchange"}
    if expected in resolution_family and actual in resolution_family:
        return True
    return False


def _fallback_decision_score(response: str, exp_action: str, item_id: str) -> dict:
    """Score when item not found in structured format — check free text."""
    text = response.lower()

    # Check if item_id is at least mentioned
    item_mentioned = item_id.lower() in text

    action_keywords = {
        "deny": ["deny", "denied", "not eligible", "cannot", "unable", "unfortunately", "ineligible"],
        "refund": ["refund", "money back", "credit back"],
        "replacement": ["replace", "reship", "send another"],
        "exchange": ["exchange", "swap"],
        "store_credit": ["store credit"],
        "shipping_credit": ["shipping credit", "$10"],
        "cancel": ["cancel", "cancellation"],
    }

    keywords = action_keywords.get(exp_action, [exp_action])
    action_found = any(kw in text for kw in keywords)

    if item_mentioned and action_found:
        return {"score": 0.6, "match": "text_fallback"}
    elif action_found:
        return {"score": 0.4, "match": "action_only_in_text"}
    else:
        return {"score": 0.0, "match": "not_found"}


# ---------------------------------------------------------------------------
# 2. Financial Accuracy (30%)
# ---------------------------------------------------------------------------

def score_financial(response: str, scenario: dict) -> dict:
    """Score whether dollar amounts in the response match expected values."""
    expected_amounts = scenario.get("expected_amounts", {})

    # Filter to numeric values only
    expected_numeric = {k: v for k, v in expected_amounts.items() if isinstance(v, (int, float)) and v > 0}

    if not expected_numeric:
        return {"score": 1.0, "details": "No amounts expected (deny/cancel scenario)"}

    parsed = parse_action_lines(response)

    # Build actual amounts from parsed action lines
    actual_amounts = {}
    for p in parsed:
        if p["amount"] is not None:
            key = f"{p['item_id']}_{p['action']}"
            actual_amounts[key] = p["amount"]

    # Also extract any $X.XX from full text as fallback
    all_amounts_in_text = [float(m.replace(",", "")) for m in re.findall(r"\$(\d[\d,]*\.?\d*)", response)]

    tolerance = 2.00  # $2 tolerance
    results = {}

    for key, exp_val in expected_numeric.items():
        # Try structured match first
        if key in actual_amounts:
            diff = abs(actual_amounts[key] - exp_val)
            if diff <= tolerance:
                results[key] = {"score": 1.0, "actual": actual_amounts[key], "method": "structured"}
            elif diff <= tolerance * 3:
                results[key] = {"score": 0.5, "actual": actual_amounts[key], "method": "structured_approx"}
            else:
                results[key] = {"score": 0.0, "actual": actual_amounts[key], "method": "structured_wrong"}
            continue

        # Fallback: check if amount appears anywhere in text
        found_in_text = any(abs(a - exp_val) <= tolerance for a in all_amounts_in_text)
        if found_in_text:
            results[key] = {"score": 0.8, "method": "text_fallback"}
        else:
            results[key] = {"score": 0.0, "method": "not_found"}

    total = len(results)
    avg = sum(v["score"] for v in results.values()) / total if total else 1.0

    return {"score": avg, "per_amount": results}


# ---------------------------------------------------------------------------
# 3. Format Compliance (20%)
# ---------------------------------------------------------------------------

def score_format(response: str, scenario: dict) -> dict:
    """Score whether the response follows the MANDATORY format."""
    expected_actions = scenario.get("expected_actions", {})
    expected_amounts = scenario.get("expected_amounts", {})
    n_expected_items = len(expected_actions)

    parsed = parse_action_lines(response)
    n_parsed = len(parsed)

    sub_scores = {}

    # 3a. Has at least one structured action line?
    sub_scores["has_action_line"] = 1.0 if n_parsed > 0 else 0.0

    # 3b. Correct number of action lines (one per item)?
    if n_expected_items > 0:
        ratio = min(n_parsed, n_expected_items) / n_expected_items
        sub_scores["item_coverage"] = ratio
    else:
        sub_scores["item_coverage"] = 1.0 if n_parsed == 0 else 0.5

    # 3c. Amount present where expected?
    has_amounts = any(p["amount"] is not None for p in parsed)
    amounts_expected = any(isinstance(v, (int, float)) and v > 0 for v in expected_amounts.values())
    if amounts_expected:
        sub_scores["amount_present"] = 1.0 if has_amounts else 0.0
    else:
        # Deny/cancel — no amount needed
        sub_scores["amount_present"] = 1.0

    # 3d. Uses separator (---) before action lines?
    sub_scores["has_separator"] = 1.0 if "---" in response else 0.5

    # Weighted average of sub-scores
    weights = {"has_action_line": 0.4, "item_coverage": 0.3, "amount_present": 0.2, "has_separator": 0.1}
    score = sum(sub_scores[k] * weights[k] for k in weights)

    return {"score": score, "sub_scores": sub_scores}


# ---------------------------------------------------------------------------
# Combined scoring
# ---------------------------------------------------------------------------

WEIGHTS = {
    "decision": 0.50,
    "financial": 0.30,
    "format": 0.20,
}


def score_scenario(response: str, scenario: dict) -> dict:
    """Score a single scenario response. Returns detailed breakdown."""
    # Check if this is a clarification scenario
    expected_resolution = scenario.get("expected_resolution", "")
    is_clarification = expected_resolution.lower().startswith("policy: clarification")
    
    if is_clarification:
        # For clarification scenarios, check if response contains "Policy: clarification"
        # and mentions order ID
        response_lower = response.lower()
        has_policy_marker = "policy:" in response_lower and "clarification" in response_lower
        mentions_order_id = "order id" in response_lower or "order number" in response_lower
        
        # Simple scoring for clarification
        if has_policy_marker and mentions_order_id:
            score = 1.0
        elif has_policy_marker or mentions_order_id:
            score = 0.7
        else:
            score = 0.3
        
        return {
            "scenario_id": scenario.get("scenario_id", "unknown"),
            "difficulty": "clarification",
            "combined": round(score, 3),
            "decision_correctness": round(score, 3),
            "financial_accuracy": 1.0,  # N/A for clarification
            "format_compliance": round(score, 3),
            "decision_details": {"score": score, "is_clarification": True},
            "financial_details": {"score": 1.0},
            "format_details": {"score": score},
        }
    
    # Normal scoring for action scenarios
    decision = score_decision(response, scenario)
    financial = score_financial(response, scenario)
    fmt = score_format(response, scenario)

    combined = (
        decision["score"] * WEIGHTS["decision"]
        + financial["score"] * WEIGHTS["financial"]
        + fmt["score"] * WEIGHTS["format"]
    )

    return {
        "scenario_id": scenario.get("scenario_id", "unknown"),
        "difficulty": scenario.get("difficulty", "unknown"),
        "combined": round(combined, 3),
        "decision_correctness": round(decision["score"], 3),
        "financial_accuracy": round(financial["score"], 3),
        "format_compliance": round(fmt["score"], 3),
        "decision_details": decision,
        "financial_details": financial,
        "format_details": fmt,
    }


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def evaluate_batch(responses: list[dict], verbose: bool = False) -> dict:
    """Evaluate a batch of (response_text, scenario) pairs.

    Args:
        responses: list of {"response": str, "scenario": dict} entries
        verbose: print per-scenario results

    Returns:
        Summary dict with averages and per-scenario breakdown.
    """
    results = []

    for i, entry in enumerate(responses):
        response_text = entry["response"]
        scenario = entry["scenario"]

        scores = score_scenario(response_text, scenario)
        scores["response_preview"] = response_text[:200]
        results.append(scores)

        if verbose:
            status = "✓" if scores["combined"] >= 0.8 else ("~" if scores["combined"] >= 0.5 else "✗")
            print(
                f"  [{i+1:>3}/{len(responses)}] {status} {scores['scenario_id']:<25} "
                f"dec={scores['decision_correctness']:.0%} "
                f"fin={scores['financial_accuracy']:.0%} "
                f"fmt={scores['format_compliance']:.0%} "
                f"→ {scores['combined']:.0%}"
            )

    n = len(results)
    if n == 0:
        return {"n_scenarios": 0, "results": []}

    def avg(key):
        return round(sum(r[key] for r in results) / n, 3)

    # Group by difficulty
    by_difficulty = {}
    for r in results:
        d = r.get("difficulty", "unknown")
        by_difficulty.setdefault(d, []).append(r)

    difficulty_summary = {}
    for d, group in by_difficulty.items():
        gn = len(group)
        difficulty_summary[d] = {
            "count": gn,
            "avg_combined": round(sum(r["combined"] for r in group) / gn, 3),
            "avg_decision": round(sum(r["decision_correctness"] for r in group) / gn, 3),
            "avg_financial": round(sum(r["financial_accuracy"] for r in group) / gn, 3),
            "avg_format": round(sum(r["format_compliance"] for r in group) / gn, 3),
        }

    return {
        "n_scenarios": n,
        "avg_combined": avg("combined"),
        "avg_decision_correctness": avg("decision_correctness"),
        "avg_financial_accuracy": avg("financial_accuracy"),
        "avg_format_compliance": avg("format_compliance"),
        "by_difficulty": difficulty_summary,
        "pass_rate": round(sum(1 for r in results if r["combined"] >= 0.8) / n, 3),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Pretty-print
# ---------------------------------------------------------------------------

def print_summary(summary: dict, model_name: str = "unknown"):
    """Print a formatted evaluation summary."""
    print(f"\n{'═' * 70}")
    print(f"  Model: {model_name}")
    print(f"  Scenarios: {summary['n_scenarios']} | Pass Rate (≥80%): {summary['pass_rate']:.0%}")
    print(f"{'═' * 70}")
    print(f"  Decision Correctness (50%):  {summary['avg_decision_correctness']:.1%}")
    print(f"  Financial Accuracy (30%):    {summary['avg_financial_accuracy']:.1%}")
    print(f"  Format Compliance (20%):     {summary['avg_format_compliance']:.1%}")
    print(f"  ─── Combined Score:          {summary['avg_combined']:.1%}")
    print(f"{'═' * 70}")

    by_diff = summary.get("by_difficulty", {})
    if by_diff:
        print(f"\n  By Difficulty:")
        for d in ["easy", "medium", "hard"]:
            if d in by_diff:
                info = by_diff[d]
                print(
                    f"    {d.upper():<8} ({info['count']:>2}): "
                    f"combined={info['avg_combined']:.0%}  "
                    f"[dec={info['avg_decision']:.0%} "
                    f"fin={info['avg_financial']:.0%} "
                    f"fmt={info['avg_format']:.0%}]"
                )
    print()


# ---------------------------------------------------------------------------
# Foundry-required grade() function
# ---------------------------------------------------------------------------
# 
# IMPORTANT: Azure AI Foundry Data Format (confirmed 2026-05-26)
# ────────────────────────────────────────────────────────────────────────
# 
# Foundry calls: grade(sample, item)
# 
# Where:
#   sample = {
#     "output": [...],  # Metadata only, NOT the response text
#     ...
#   }
# 
#   item = {
#     "sample.output_text": "Agent response here...",  # ← THE RESPONSE TEXT
#     "expected_actions": {...},                       # ← Expected actions dict
#     "expected_amounts": {...},                       # ← Expected amounts dict
#     "scenario_id": "...",
#     "difficulty": "...",
#     ...
#   }
# 
# Key insight: Foundry injects the agent's output into the ITEM dict,
#              not the SAMPLE dict. This is why item['sample.output_text']
#              contains the text we need to grade.
# 
# ────────────────────────────────────────────────────────────────────────

def grade(sample: dict, item: dict) -> float:
    """
    Top-level grading function required by Azure AI Foundry.
    
    Based on actual Foundry behavior (confirmed 2026-05-26):
    - Foundry passes the agent output text in the ITEM parameter, not SAMPLE
    - Specifically at: item['sample.output_text']
    - The item also contains all dataset fields (expected_actions, expected_amounts, etc.)
    
    Args:
        sample: Model output metadata (not used - Foundry doesn't put text here)
        item: Dataset row with agent output injected:
              - item['sample.output_text']: Agent's response text (REQUIRED)
              - item['expected_actions']: Expected actions dict (REQUIRED)
              - item['expected_amounts']: Expected amounts dict (REQUIRED)
              - item['scenario_id']: Scenario identifier
              - item['difficulty']: Difficulty level
    
    Returns:
        float: Score between 0.0 and 1.0
    """
    # Extract response text from item (Foundry's confirmed location)
    if not isinstance(item, dict):
        raise ValueError(f"Expected item to be dict, got {type(item)}")
    
    response_text = item.get('sample.output_text', '')
    
    if not response_text:
        # This should not happen if Foundry is working correctly
        raise ValueError(
            "No response text found in item['sample.output_text']. "
            "Foundry should inject this field. Available keys: " + str(list(item.keys()))
        )
    
    # Score using existing logic
    result = score_scenario(response_text, item)
    
    # Return the combined score (0.0 - 1.0)
    return result['combined']
