"""Retail Multi-Tool Agent — 6-tool agentic workflow for post-purchase resolution.

The model calls tools in sequence to gather info, check policy, calculate amounts,
and submit resolutions. Policy logic is in the tools, not the model.
"""

import json
import logging
import os

import httpx
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
    TextResponse,
)
from azure.ai.agentserver.responses.models import (
    MessageContentInputTextContent,
    MessageContentOutputTextContent,
)
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

from tracing import trace_agent_invocation, trace_chat_completion


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_URL = os.environ.get("TOOL_URL", "https://retail-tools-omkarm.azurewebsites.net")

SYSTEM_PROMPT = """\
# Retail Post-Purchase Resolution Agent

You are Retail's post-purchase resolution agent. You help customers with returns, exchanges, replacements, cancellations, and shipping disputes.

## Interaction Rules
- You should at most make one tool call at a time. If you make a tool call, do not respond to the user at the same time.
- If you respond to the user, do not make a tool call.
- You should not make up any information not provided by the user or the tools.
- If the customer does not provide an order ID, ask for it before taking any action.
- For each item, address it separately. Cite the specific policy when denying.

## Domain Knowledge

### Return Windows (from delivery date)
| Tier      | Apparel/Home | Electronics | Personal Care      |
|-----------|-------------|-------------|--------------------|
| Standard  | 30 days     | 15 days     | 15 days (sealed)   |
| Gold      | 45 days     | 30 days     | 30 days (sealed)   |
| Platinum  | 60 days     | 45 days     | 45 days (sealed)   |

Electronics includes: headphones, keyboards, speakers, watches, kettles, lamps.

### Restocking Fees
- Apparel/home: NO restocking fee
- Electronics (non-defective): Standard 15%, Gold 7.5%, Platinum 0%
- Defective items: ALWAYS 0% restocking fee

### Special Cases
- Sale items: Final sale (no returns/exchanges); defective sale items -> store credit ONLY.
- Late delivery (>2 days past promise): $10 shipping credit per late item, return window extended +15 days.
- Lost packages: full replacement OR full refund; no restocking fee.
- Cancellations: only if order status is pending or processing; full refund.
- Defective: ALWAYS eligible regardless of window, sale status, or category. No restocking fee.
- Personal care: cannot return once opened, unless defective.

## Response Format
After resolving, provide a summary line for EACH item in this exact format:
- For approved actions: Action: <action> for <item_id> (reason: <reason>). Amount: $<amount>.
- For denied actions: Action: deny for <item_id> (reason: <denial_reason>).
- For cancellations: Action: cancel for <item_id> (reason: cancellation).
- If clarification is needed: Policy: clarification, <what_is_needed>.

Where <action> is one of: refund, exchange, replacement, store_credit, shipping_credit, cancel, deny.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": (
                "Retrieve order details: line items (item_id, product_name, category, "
                "sku, quantity, unit_price, discount_pct, on_sale), customer info (name, "
                "email, loyalty_tier), payment method, dates, subtotal, tax, total. "
                "Always call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID, e.g. 'ORD-001'"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fulfillment_status",
            "description": (
                "Get per-item shipping/fulfillment status. Returns each item's status "
                "(processing/shipped/delivered/lost), ship_date, delivery_date, carrier, "
                "late_delivery flag, days_late, and days_since_delivery."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_resolution_policy",
            "description": (
                "Check resolution eligibility for ONE item. Returns: eligible (bool), "
                "eligible_actions, return_window_days, days_since_delivery, "
                "restocking_fee_pct, shipping_credit, special_rules, denial_reason. "
                "Call once PER item needing resolution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "item_id": {"type": "string", "description": "The line item ID, e.g. 'LI-002'"},
                    "reason": {
                        "type": "string",
                        "description": (
                            "Customer's reason: 'defective', 'buyers_remorse', "
                            "'wrong_item', 'doesnt_fit', 'changed_mind', "
                            "'damaged_in_shipping', or 'opened_not_needed'."
                        ),
                    },
                },
                "required": ["order_id", "item_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": (
                "Check stock for a SKU. Returns in_stock, quantity, restock_date "
                "(if OOS), and alternative in-stock variants. "
                "Call ONLY when processing an exchange."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU, e.g. 'P007-9' or 'P003-M'"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_resolution",
            "description": (
                "Calculate financial details for a resolution plan. Takes a list of "
                "item actions with item_id, action (refund/exchange/replacement/"
                "store_credit/deny/shipping_credit), reason, and optionally "
                "exchange_sku. Returns per-item breakdown and totals. "
                "Always call check_resolution_policy FIRST."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "items": {
                        "type": "array",
                        "description": "List of item resolution actions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "string"},
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "refund", "exchange", "replacement",
                                        "store_credit", "deny", "shipping_credit",
                                    ],
                                },
                                "reason": {"type": "string"},
                                "exchange_sku": {"type": "string"},
                            },
                            "required": ["item_id", "action", "reason"],
                        },
                    },
                },
                "required": ["order_id", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_resolution",
            "description": (
                "Submit the final resolution for processing. Returns a confirmation "
                "ID. ONLY call after calculate_resolution confirms the amounts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                    "resolution_summary": {
                        "type": "string",
                        "description": "Text summary of the resolution being submitted",
                    },
                },
                "required": ["order_id", "resolution_summary"],
            },
        },
    },
]


def call_tool(name: str, arguments: dict) -> str:
    """Execute a tool by calling our remote FastAPI endpoint."""
    try:
        payload = {
            "arguments": arguments if isinstance(arguments, dict) else json.loads(arguments),
            "call_id": "",
            "id": "",
        }
        r = httpx.post(f"{TOOL_URL}/tool/{name}", json=payload, timeout=30)
        if r.status_code != 200:
            return f"Error: {r.status_code} - {r.text}"
        resp = r.json()
        return resp.get("output", r.text)
    except Exception as e:
        return f"Tool error: {e}"


def get_openai_client():
    """Build an OpenAI client via Foundry AIProjectClient."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    return project_client.get_openai_client()


async def run_agent(messages: list[dict], max_turns: int = 12) -> str:
    """Run the multi-tool agent loop."""
    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "qwen3-32b-base")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    for _ in range(max_turns):
        with trace_chat_completion(
            model=model,
            messages=messages,
            tools=TOOLS,
        ) as chat_trace:
            response = await openai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
            )
            chat_trace.set_response(response)

        choice = response.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = call_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "I apologize, but I was unable to complete the resolution within the allowed number of steps."


# --- Hosted Agent Server (Responses protocol) ---

app = ResponsesAgentServerHost(options=ResponsesServerOptions(default_fetch_history_count=20))
openai_client = get_openai_client()


@app.response_handler
async def handle_create(request: CreateResponse, context: ResponseContext, cancellation_signal):
    """Handle incoming responses requests."""
    current_input = await context.get_input_text()

    try:
        history = await context.get_history()
    except Exception:
        history = []

    history_messages = []
    for item in history:
        if hasattr(item, "content") and item.content:
            for content in item.content:
                if isinstance(content, MessageContentOutputTextContent) and content.text:
                    history_messages.append({"role": "assistant", "content": content.text})
                elif isinstance(content, MessageContentInputTextContent) and content.text:
                    history_messages.append({"role": "user", "content": content.text})

    logging.info("Executing agent with input: '%s' and history: %s", current_input, history_messages)
    messages = [*history_messages, {"role": "user", "content": current_input}]
    with trace_agent_invocation(messages=messages) as agent_trace:
        result = await run_agent(messages)
        agent_trace.set_output(result)
    return TextResponse(context, request, text=result)


if __name__ == "__main__":
    app.run()
