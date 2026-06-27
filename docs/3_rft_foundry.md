# Phase 3: Reinforcement Fine-Tuning — o4-mini with Foundry SDK

**Demo Time:** 10-12 minutes

---

## 🎯 What the Audience Should Walk Away With

1. How RFT differs from SFT (trial-and-error vs imitation)
2. How a custom grader provides the reward signal
3. How easy it is to submit RFT jobs with the Foundry SDK
4. That RFT achieves 82.3% on o4-mini (up from 71% base)
5. The power of letting the model explore and learn from mistakes

---

## 🎬 Demo Script

### 1. SFT vs RFT — Why Go Further? (2 min)

**Key Message:** "SFT teaches by showing. RFT teaches by doing. The model tries, gets scored, and improves."

**Visual:**
```
SFT (Phase 2):                    RFT (Phase 3):
┌─────────────┐                   ┌─────────────┐
│   Teacher   │                   │   Grader    │ ← Automated judge
│  (GPT-5.4)  │                   │  (Python)   │
└──────┬──────┘                   └──────┬──────┘
       │ "Here's the                     │ "You scored 0.7,
       │  right answer"                  │  here's why..."
       ▼                                 ▼
┌─────────────┐                   ┌─────────────┐
│   Student   │                   │   o4-mini   │
│   learns    │                   │   explores  │ ← Tries different approaches
│   to copy   │                   │   & learns  │    Gets reward/penalty
└─────────────┘                   └─────────────┘
```

**Why RFT on top of SFT?**
- SFT ceiling: student can only match teacher (and teacher is 64.5%)
- RFT breakthrough: model discovers *new* strategies the teacher never showed
- Result: o4-mini-finetuned reaches **82.3%** — far beyond teacher's 64.5%

---

### 2. The Grader — Your Reward Function (3 min)

**Show:** `scripts/retail_grader_rft_tools.py`

**Explain the scoring:**
```python
# The grader scores each attempt on 4 dimensions:
score = (
    0.35 * action_correctness +    # Right decision? (refund/deny/exchange)
    0.25 * amount_accuracy +       # Correct dollar amounts?
    0.25 * tool_coverage +         # Called the right tools?
    0.15 * workflow_compliance     # Correct tool order?
)
```

**Key Insight:** "This grader IS the reward model. The model gets tools, tries to solve the scenario, and the grader scores the attempt. No human in the loop — fully automated RL."

**Show:** How tool access works during training:
- The model has access to real tools during training
- It calls `get_order_details`, `check_resolution_policy`, etc.
- The grader validates the entire conversation including tool usage
- This is what makes it "agentic" fine-tuning

---

### 3. Submit RFT Job with Foundry SDK (3 min)

**Show:** `notebooks/phase3_submit_rft.ipynb`

**The API call:**
```python
job = client.fine_tuning.jobs.create(
    model="o4-mini",
    training_file=train_file.id,
    validation_file=val_file.id,
    suffix="retail-rft",
    method={
        "type": "reinforcement",
        "reinforcement": {
            "grader": {
                "type": "python",
                "name": "retail_quality",
                "source": GRADER_SOURCE,
                "pass_threshold": 0.80,
            },
            "tools": TOOL_CONFIG,          # 6 tools available during training
            "max_episode_steps": 5,
            "hyperparameters": {
                "n_epochs": 3,
                "reasoning_effort": "medium",
            },
        }
    },
)
```

**Key Points to Emphasize:**
- Same SDK, just change `method.type` from `supervised_fine_tuning` to `reinforcement`
- Grader source is inline Python — no external service needed
- Tools are configured so the model can practice during training
- `max_episode_steps`: how many tool calls per attempt
- Azure manages the RL loop: generate → grade → update → repeat

---

### 4. Results — Best Performance Yet (2 min)

**Show:** Final comparison

| Model | Approach | retail_quality |
|-------|----------|:---:|
| o4-mini (base) | — | 71.0% |
| o4-mini-finetuned (RFT) | Reinforcement | **82.3%** |
| gpt-4-1-mini-finetuned (SFT) | Distillation | 71.0% |
| gpt-5.4 (teacher) | — | 64.5% |

**The Punchline:** "RFT gives us 82.3% — 11.3 points above the base model and 17.8 points above the teacher. The model learned strategies that nobody explicitly taught it."

**Why o4-mini is ideal for RFT:**
- Reasoning model — benefits from exploration
- Already has strong tool-calling capabilities
- RFT refines its decision-making, not just its format

---

### 5. What Changed? (2 min)

**Show:** Before/after on specific failure scenarios

**Example — Sale item exchange:**
- **Before (base o4-mini):** Tries to process exchange, ignores "final sale" policy
- **After (RFT o4-mini):** Correctly identifies sale item → offers store credit only

**Example — Multi-item order:**
- **Before:** Processes first item, forgets second
- **After:** Resolves each item independently with correct per-item calculations

---

## 📁 Key Files for This Phase

| File | Purpose |
|------|---------|
| `scripts/retail_grader_rft_tools.py` | Grader (reward function) |
| `data/retail_train.jsonl` | Training scenarios (481) |
| `data/retail_val.jsonl` | Validation scenarios (62) |
| `notebooks/phase3_submit_rft.ipynb` | RFT job submission |
| `deploy/src/retail-o4-mini-finetuned/` | Deployed RFT agent |

---

## 🔗 Next

**[→ Phase 4: Low-Level RFT on Qwen3-32B](4_rft_lowlevel.md)** — Maximum control with tinker APIs on an open-source model
