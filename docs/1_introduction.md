# Phase 1: Introduction — The Retail Agent & Why Fine-Tuning Matters

**Demo Time:** 12-15 minutes

---

## 🎯 What the Audience Should Walk Away With

1. Understanding of the Retail agent scenario (6-tool post-purchase resolution)
2. How the production agent (GPT-5.4) works today
3. How traces from production generate evaluations
4. The "execution gap" — base models struggle with complex tool orchestration
5. A preview of 3 improvement paths: SFT distillation → RFT → Low-level RFT

---

## 🎬 Demo Script

### 1. The Retail Scenario (3 min)

**Story:** "We have a production AI agent handling post-purchase customer service — returns, exchanges, replacements. It's powered by GPT-5.4 and works well, but it's expensive. Can we get the same quality from smaller, cheaper models?"

**Show:** Open `tools/retail-tools/demo.html` (live at https://retail-tools-omkarm.azurewebsites.net/demo)

**Walk through:**
- The 6 tools and their orchestration flow
- Database viewer: customers, products, orders
- Invoke a tool live to show the API

**The 6-Tool Workflow:**
```
get_order_details → get_fulfillment_status → check_resolution_policy
    → check_inventory (exchanges only) → calculate_resolution → submit_resolution
```

**Why this is hard:**
- Multi-step tool orchestration (3-6 calls per scenario)
- Complex policy rules (loyalty tiers × categories × delivery status)
- Precise financial calculations (restocking fees, credits)
- Edge cases: sale items, lost packages, late deliveries, defective items

---

### 2. The Production Agent (3 min)

**Show:** `agents/retail/main.py` — single codebase for all model variants
*(This is the source of truth; it gets copied to each `deploy/src/<agent>/main.py` for deployment.)*

**Key Points:**
- Production runs on GPT-5.4 (`retail-prod` agent)
- Same code, different model via `AZURE_AI_MODEL_DEPLOYMENT_NAME` env var
- Deployed as hosted agent on Azure AI Foundry
- All tool calls go to the Function App

**Demo:** Open Foundry UI → Agent Playground
- Select `retail-prod` agent
- Send a message: *"Noah Brown. I changed my mind on the Bluetooth Speaker from ORD-010, can I return it?"*
- Show the agent resolving the scenario live

**Show Traces:** Foundry portal → Tracing tab
- Full tool-call chain visible (get_order_details → check_resolution_policy → calculate_resolution → submit_resolution)
- Latency per step
- Token usage
- "These traces are gold — they tell us what the right answer looks like"

---

### 3. From Traces to Evaluations (5 min)

**Key Insight:** "Production traces give us two superpowers:"
1. **Distillation data** — We can use prod traces (GPT-5.4 outputs) to teach smaller models via SFT, saving costs
2. **Evaluation data** — Add ground truth / human annotations to traces → use as eval dataset for measuring any model

**Demo in Foundry UI:**
- Show tracing tab → select traces → **Export to evaluation dataset**
- Show the exported dataset format (input message + expected output)
- "In practice you'd also add human annotations for edge cases"

**Introduce the Grader:** `scripts/retail_grader_response.py`
- Custom Python grader that scores agent responses
- Only depends on the final response (no access to intermediate tool calls)
- Scoring: action correctness (50%) + financial accuracy (30%) + format (20%)
- Same grader used across all models → apples-to-apples comparison

**Run Evaluations on Base Models:**
- **Show:** `notebooks/phase2_base_evaluations.ipynb`
- Trigger eval run for all base models (gpt-5.4, o4-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano)
- "These are base models — no fine-tuning yet"

**Show Results in Foundry UI:**
- Open a completed eval run
- Show the leaderboard / comparison view across models

**Key Results:**

| Model | retail_quality | Cost/scenario |
|-------|:---:|---|
| gpt-5.4 (prod) | 64.5% | $$$ |
| o4-mini | 71.0% | $$ |
| gpt-4.1 | 58.1% | $ |
| gpt-4.1-mini | 45.2% | ¢ |
| gpt-4.1-nano | 1.6% | ¢ |

---

### 4. The Execution Gap & Promise (2 min)

**The Gap:** "Most base models understand the intent correctly, but fail at execution — wrong tool order, wrong calculations, missed policy rules. They know WHAT to do but not HOW."

**The Promise:** "We'll fix this with fine-tuning. Three approaches, progressive control:"

1. **SFT Distillation** (easiest API) — Teach smaller models by showing them GPT-5.4's traces
2. **RFT with Foundry SDK** (powerful SDK) — Let o4-mini learn from trial-and-error with the grader as reward
3. **Low-level RFT APIs** (maximum control) — Fine-grained training on OSS Qwen3-32B with tinker APIs

---

## 📁 Key Files for This Phase

| File | Purpose |
|------|---------|
| `tools/retail-tools/function_app.py` | Tool server (6 endpoints) |
| `tools/retail-tools/demo.html` | Interactive demo console |
| `agents/retail/main.py` | Agent source code |
| `data/retail_eval.jsonl` | 62 evaluation scenarios |
| `data/dashboard.html` | Data explorer |
| `scripts/retail_grader_response.py` | Custom Python grader |
| `notebooks/phase2_base_evaluations.ipynb` | Multi-model eval notebook |

---

## 🔗 Next

**[→ Phase 2: SFT Distillation](2_sft_distillation.md)** — Distill GPT-5.4 knowledge into smaller models
