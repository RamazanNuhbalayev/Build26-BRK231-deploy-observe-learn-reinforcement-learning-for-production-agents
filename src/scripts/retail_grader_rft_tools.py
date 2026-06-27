"""
Retail RFT Grader with Tool Call Scoring - For Reinforcement Fine-Tuning
Created: 2026-05-27, Updated: 2026-05-27

Enhanced grader that incorporates expected_tools from the reference dataset.
Rewards the model for making the correct tool calls while allowing flexibility
in ordering and exploration (extra tool calls are not penalized).

Data access pattern (critical for RFT):
  - sample['output_text']: Model's generated text response
  - sample['output_tools']: Model's tool calls during the episode
  - item['expected_resolution']: Ground truth from dataset
  - item['expected_tools']: Expected tool calls from dataset

Scoring breakdown:
  - Action/Decision Match: 35% (correct refund/exchange/deny/etc.)
  - Financial Amounts: 25% (correct dollar amounts within 2¢)
  - Tool Coverage: 25% (called all expected tools from reference)
  - Tool Workflow Quality: 15% (logical ordering + no hallucinated tools)
"""

import json
import re


# All valid tools the agent can call
VALID_TOOLS = {
    "get_order_details",
    "get_fulfillment_status",
    "check_resolution_policy",
    "check_inventory",
    "calculate_resolution",
    "submit_resolution",
}

# Logical ordering constraints (tool A should come before tool B)
# We only penalize gross violations, not minor reorderings
ORDERING_CONSTRAINTS = [
    ("get_order_details", "check_resolution_policy"),
    ("get_order_details", "calculate_resolution"),
    ("check_resolution_policy", "calculate_resolution"),
    ("calculate_resolution", "submit_resolution"),
]


def _extract_tool_names(output_tools):
    """Extract tool names from various tool call formats."""
    tool_names = []
    if not output_tools:
        return tool_names

    for t in output_tools:
        if isinstance(t, dict):
            name = (
                t.get("name")
                or t.get("function", {}).get("name")
                or t.get("tool_name")
                or ""
            )
            if name:
                tool_names.append(name)
        elif isinstance(t, str):
            tool_names.append(t)

    return tool_names


def _score_tool_coverage(actual_tools, expected_tools):
    """
    Score based on whether the model called all expected tools.
    
    - Each expected tool present in actual calls earns equal credit.
    - Extra tools are NOT penalized (model is free to explore).
    - Duplicate calls of the same tool are fine (e.g., multiple check_resolution_policy).
    
    Returns: float between 0.0 and 1.0
    """
    if not expected_tools:
        return 1.0  # No expectations = full credit

    actual_set = set(actual_tools)
    expected_set = set(expected_tools)

    hits = len(expected_set & actual_set)
    return hits / len(expected_set)


def _score_tool_workflow(actual_tools):
    """
    Score the quality of tool ordering and validity.
    
    - Rewards logical ordering (get_order_details before calculate_resolution, etc.)
    - Penalizes hallucinated tool names (tools not in VALID_TOOLS)
    - Does NOT penalize extra valid tool calls or repeated calls
    
    Returns: float between 0.0 and 1.0
    """
    if not actual_tools:
        return 0.0

    score = 1.0

    # Check for hallucinated tools (not in valid set)
    valid_calls = [t for t in actual_tools if t in VALID_TOOLS]
    invalid_calls = [t for t in actual_tools if t not in VALID_TOOLS]

    if invalid_calls:
        # Penalize proportionally to invalid calls
        invalid_ratio = len(invalid_calls) / len(actual_tools)
        score -= 0.5 * invalid_ratio

    # Check ordering constraints (only among valid calls)
    if len(valid_calls) >= 2:
        violations = 0
        total_constraints = 0

        for before, after in ORDERING_CONSTRAINTS:
            # Only check if both tools are present
            if before in valid_calls and after in valid_calls:
                total_constraints += 1
                # Find first occurrence of each
                first_before = next(
                    (i for i, t in enumerate(valid_calls) if t == before), None
                )
                first_after = next(
                    (i for i, t in enumerate(valid_calls) if t == after), None
                )
                if first_before is not None and first_after is not None:
                    if first_before > first_after:
                        violations += 1

        if total_constraints > 0:
            ordering_penalty = 0.5 * (violations / total_constraints)
            score -= ordering_penalty

    return max(score, 0.0)


def grade(sample, item):
    """
    Grade agent response for RFT training with tool call awareness.
    
    Args:
        sample: Model output from training:
              - sample['output_text']: The model's final text response
              - sample['output_tools']: Tool calls the model made
        item: Dataset row (ground truth):
              - item['expected_tools']: Reference tool calls from dataset
              - item['expected_resolution']: Expected resolution from dataset
    
    Returns:
        float: Score between 0.0 and 1.0
    """
    # =========================================================================
    # EXTRACT MODEL OUTPUT (from sample)
    # =========================================================================
    # Note: don't hard-zero on empty output_text — a tool-only turn (no final
    # text) should still get partial credit from the tool components so the
    # RFT signal isn't killed for otherwise-correct rollouts.
    output_text = sample.get("output_text", "") or ""

    output_tools = sample.get("output_tools", []) or []
    actual_tool_names = _extract_tool_names(output_tools)

    # =========================================================================
    # EXTRACT GROUND TRUTH (from item/dataset)
    # =========================================================================
    expected_tools = item.get("expected_tools", []) or []
    expected = item.get("expected_resolution", "")
    if not expected:
        return 0.0

    out_lower = output_text.lower()
    exp_lower = expected.lower()
    score = 0.0

    # =========================================================================
    # 1. CLARIFICATION SCENARIOS (Policy: clarification)
    # =========================================================================
    if exp_lower.startswith("policy: clarification"):
        has_clarification = "policy: clarification" in out_lower
        has_order_ref = any(k in out_lower for k in [
            "order id", "order_id", "which order", "order number",
            "provide your order", "provide the order"
        ])

        # For clarification, tool usage is less critical but still valued
        tool_coverage = _score_tool_coverage(actual_tool_names, expected_tools)

        if has_clarification and has_order_ref:
            base = 0.85
        elif has_clarification or has_order_ref:
            base = 0.55
        else:
            base = 0.2

        # Add tool bonus (up to 0.15 for clarification scenarios)
        return round(min(base + 0.15 * tool_coverage, 1.0), 3)

    # =========================================================================
    # 2. ACTION SCENARIOS (Specific resolutions)
    # =========================================================================

    action_keywords = {
        "deny": ["denied", "deny", "not eligible", "cannot", "expired", "unable", "not returnable"],
        "cancel": ["cancel", "cancellation"],
        "store credit": ["store credit", "store_credit"],
        "exchange": ["exchange", "swap"],
        "replacement": ["replacement", "replace"],
        "refund": ["refund"],
    }

    # -------------------------------------------------------------------------
    # Component 1: Action/Decision Match (35% weight)
    # -------------------------------------------------------------------------
    action_matches = re.findall(r'action:\s*(\w+(?:\s+\w+)?)', exp_lower)

    if action_matches:
        hits = 0
        for act in action_matches:
            keywords = action_keywords.get(act.strip(), [act.strip()])
            if any(k in out_lower for k in keywords):
                hits += 1
        score += 0.35 * (hits / len(action_matches))

    # -------------------------------------------------------------------------
    # Component 2: Financial Amount Match (25% weight)
    # -------------------------------------------------------------------------
    exp_amounts = re.findall(r'\$(\d+\.?\d{0,2})', expected)

    if exp_amounts:
        out_amounts = re.findall(r'\$\s*(\d+(?:\.\d{1,2})?)', output_text)
        out_floats = {round(float(a), 2) for a in out_amounts}

        # Match ALL expected amounts (including $0.00)
        hits = sum(1 for a in exp_amounts if any(abs(float(a) - o) < 0.02 for o in out_floats))
        score += 0.25 * (hits / len(exp_amounts))
    else:
        # No amounts mentioned at all (e.g., deny with no dollar figure)
        score += 0.25

    # -------------------------------------------------------------------------
    # Component 3: Tool Coverage (25% weight)
    # Uses expected_tools from the reference dataset
    # Only penalize if reference expects tool calls
    # -------------------------------------------------------------------------
    if expected_tools:
        tool_coverage = _score_tool_coverage(actual_tool_names, expected_tools)
        score += 0.25 * tool_coverage
    else:
        # No tools expected in reference — full credit
        score += 0.25

    # -------------------------------------------------------------------------
    # Component 4: Tool Workflow Quality (15% weight)
    # Rewards logical ordering, penalizes hallucinated tools
    # Only penalize if reference expects tool calls
    # -------------------------------------------------------------------------
    if expected_tools:
        if actual_tool_names:
            workflow_score = _score_tool_workflow(actual_tool_names)
            score += 0.15 * workflow_score
        # If tools expected but none called, this stays at 0
    else:
        # No tools expected in reference — full credit
        score += 0.15

    # =========================================================================
    # FINAL SCORE
    # =========================================================================
    return round(min(score, 1.0), 3)


# =============================================================================
# GRADER METADATA
# =============================================================================
# Pass Threshold: 0.80
# Scoring Breakdown:
#   - Action/Decision Match: 35% (correct refund/exchange/deny/etc.)
#   - Financial Amounts: 25% (correct dollar amounts within 2¢)
#   - Tool Coverage: 25% (called all expected tools from reference)
#   - Tool Workflow Quality: 15% (logical ordering, no hallucinated tools)
#
# Tool Scoring Philosophy:
#   - Coverage rewards calling the RIGHT tools (from expected_tools)
#   - Order is softly enforced (only gross violations penalized)
#   - Extra tool calls are NOT penalized (exploration is allowed)
#   - Repeated calls of same tool are fine (e.g., multiple policy checks)
#   - Hallucinated tool names (not in valid set) are penalized
#
# Data Format (RFT Training):
#   - sample['output_text']: Model's generated text response
#   - sample['output_tools']: Model's tool calls (list of dicts with "function.name")
#   - item['expected_tools']: Reference tool list from dataset
#   - item['expected_resolution']: Ground truth from dataset
# =============================================================================
