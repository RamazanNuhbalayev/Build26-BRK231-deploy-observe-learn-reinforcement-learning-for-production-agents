# Phase 4: Low-Level RFT — Qwen3-32B with Tinker APIs

**Demo Time:** 8-10 minutes

---

## 🎯 What the Audience Should Walk Away With

1. What the low-level "tinker" APIs provide vs the high-level SDK
2. Why you'd choose this: full control over training hyperparameters, checkpointing, reward shaping
3. How to fine-tune an open-source model (Qwen3-32B) on Azure AI Foundry
4. That OSS models can compete with proprietary models when properly trained
5. The full leaderboard: from 1.6% (nano base) to 86.9% (Qwen3-32B RFT)

---

## 🎬 Demo Script

### 1. Why Low-Level APIs? (2 min)

**Key Message:** "The Foundry SDK makes fine-tuning easy. But sometimes you need more control — custom learning rates, checkpoint selection, reward shaping, early stopping. That's what our low-level APIs give you."

**Comparison:**

| Feature | Foundry SDK (Phase 3) | Low-Level APIs (Phase 4) |
|---------|:---:|:---:|
| Submit job | ✅ One API call | ✅ One API call |
| Custom grader | ✅ Inline Python | ✅ Inline Python |
| Hyperparameters | Basic (epochs, lr) | **Full control** (warmup, decay, batch size, etc.) |
| Checkpointing | Automatic best | **Manual checkpoint selection** |
| Reward shaping | Fixed scoring | **Custom reward curves** |
| Training visibility | Job status | **Step-by-step metrics** |
| Model support | OpenAI models | **Any model on Foundry (incl. OSS)** |

**When to use low-level APIs:**
- Training OSS models (Qwen, Llama, Mistral)
- Need to pick specific checkpoints (not just "best")
- Want to tune reward shaping or curriculum
- Need maximum reproducibility

---

### 2. Qwen3-32B — Open Source Contender (2 min)

**Key Message:** "Let's take an open-source model with zero Retail-specific training and push it past our best proprietary fine-tunes."

**The starting point:**
- Qwen3-32B (base) on retail_quality: **58.1%**
- For reference: GPT-5.4 (teacher) = 64.5%, o4-mini-finetuned = 82.3%, and Qwen3-32B-finetuned reaches 86.9%

**Why Qwen3-32B?**
- 32B parameters — large enough for complex reasoning
- Open weights — you own the model
- Available on Azure AI Foundry via Serverless API
- Good base tool-calling capabilities

---

### 3. Training with Low-Level Control (3 min)

**Show:** Training configuration with full hyperparameter control

```python
job = client.fine_tuning.jobs.create(
    model="qwen3-32b",
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
            "tools": TOOL_CONFIG,
            "max_episode_steps": 5,
            "hyperparameters": {
                "n_epochs": 3,
                "learning_rate_multiplier": 1.0,
                "compute_multiplier": 1.5,
                "reasoning_effort": "medium",
                "eval_interval": 5,
                "eval_samples": 10,
            },
        }
    },
)
```

**Key Differences from Phase 3:**
- `compute_multiplier`: 1.5x more compute for thorough exploration
- `eval_interval`: evaluate every 5 steps (see progress in real-time)
- `eval_samples`: 10 scenarios per eval checkpoint
- Can observe training curves and pick the best checkpoint

**Show:** Training metrics dashboard (if available)
- Reward curve over training steps
- Multiple checkpoints available
- Select checkpoint based on validation performance, not just final

---

### 4. Cross-Region Deployment (1 min)

**Key Point:** "OSS models train in specific regions (UAE North for Qwen). We deploy cross-region to our project in North Central US."

```bash
# Cross-region deployment from training region
az rest --method PUT \
  --uri ".../deployments/qwen3-32b-ft-1" \
  --body '{
    "sku": {"name": "GlobalStandard", "capacity": 100},
    "properties": {
      "model": {
        "name": "qwen3-32b.ft-model_410a16b3-lm:ckpt-step-18",
        "source": "/subscriptions/.../omi-build-demo-uae-resource"
      }
    }
  }'
```

**Note the checkpoint selection:** `ckpt-step-18` — we picked the best checkpoint from training, not just the final one.

---

### 5. Final Leaderboard (2 min)

**Show:** Complete results across all approaches

| Model | Approach | retail_quality | Phase |
|-------|----------|:---:|:---:|
| **qwen3-32b-finetuned** | RFT (Low-level) | **86.9%** | 4 |
| o4-mini-finetuned | RFT (Foundry SDK) | 82.3% | 3 |
| gpt-4.1-mini-finetuned | SFT Distillation | 71.0% | 2 |
| o4-mini (base) | — | 71.0% | — |
| gpt-5.4 (teacher/prod) | — | 64.5% | — |
| gpt-4.1 (base) | — | 58.1% | — |
| qwen3-32b (base) | — | 58.1% | — |
| gpt-4.1-mini (base) | — | 45.2% | — |
| gpt-4.1-nano-finetuned | SFT Distillation | 37.1% | 2 |
| gpt-4.1-nano (base) | — | 1.6% | — |

**Key Takeaways:**
1. **SFT is the easiest win** — GPT-4.1-mini jumps from 45.2% to 71.0%, and GPT-4.1-nano reaches 37.1%
2. **RFT pushes further** — o4-mini goes from 71.0% to 82.3% through exploration
3. **OSS models can lead** — Qwen3-32B goes from 58.1% to 86.9% with low-level RFT
4. **The best model is open** — Qwen3-32B RFT beats the 64.5% teacher by a wide margin

**Closing Message:** "Three levels of control, one SDK. Whether you want a quick distillation win or full-control training on your own model, Azure AI Foundry has you covered."

---

## 📁 Key Files for This Phase

| File | Purpose |
|------|---------|
| `notebooks/phase3_submit_rft.ipynb` | Training job submission |
| `scripts/retail_grader_rft_tools.py` | Grader (same as Phase 3) |
| `data/retail_train.jsonl` | Training data (same) |
| `deploy/src/retail-qwen3-32b-base/` | Base Qwen agent |
| `deploy/src/retail-qwen3-32b-finetuned/` | Fine-tuned Qwen agent |

---

## 🏁 Demo Complete

**Summary of the journey:**
1. ✅ Started with expensive prod agent (GPT-5.4, 64.5%)
2. ✅ Distilled to cheaper models (GPT-4.1-mini → 71.0%, nano → 37.1%) via SFT
3. ✅ Pushed further with RL (o4-mini → 82.3%) via RFT
4. ✅ Reached the overall best result with OSS RFT (Qwen3-32B → 86.9%)
5. ✅ All using the same evaluation framework and grader

**Call to Action:** "All code, notebooks, and data are in this repo. Try it on your own agents!"
