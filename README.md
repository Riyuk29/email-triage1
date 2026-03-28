---
title: Email Triage
emoji: "📧"
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# 📧 Email Triage OpenEnv

[![OpenEnv](https://img.shields.io/badge/OpenEnv-v1.0-blue)](https://github.com/meta-pytorch/OpenEnv)
[![HF Spaces](https://img.shields.io/badge/🤗%20HF%20Spaces-Deploy-yellow)](https://huggingface.co/spaces)
[![License](https://img.shields.io/badge/License-Apache%202.0-green)](LICENSE)

A real-world OpenEnv-compliant reinforcement learning environment where agents learn to **triage business emails** — classifying, prioritizing, routing, and responding to realistic inbox scenarios.

> **Why this domain?** Email triage is something every knowledge worker does daily. Getting it wrong has real consequences: missed legal notices, lost enterprise customers, ignored security disclosures. This environment is designed to train and evaluate agents that handle this task with judgment, not just keyword matching.

---

## 🎯 Environment Overview

The agent works through an inbox of realistic business emails and must take the right action for each one. Emails range from obvious spam to nuanced situations like SEC inquiries, whistleblower reports, and acquisition conversations.

### What makes it hard
- **Priority subtlety**: A billing dispute from a $180k/yr customer is more urgent than one from a free user
- **Category ambiguity**: Is a partnership inquiry a `sales_inquiry` or `partnership`? Partial credit handles this
- **Multi-intent emails**: Some need both classification and a drafted response
- **Stakes escalation**: Task 3 has emails where wrong routing has severe simulated consequences

---

## 🗂 Action Space

Every step the agent submits an `action` JSON object:

```json
{
  "action_type": "classify",
  "category": "customer_complaint",
  "priority": "urgent",
  "department": "support",
  "reasoning": "Customer threatens to post on Twitter, has been a customer 3 years"
}
```

| Field | Type | Values | Required |
|-------|------|---------|----------|
| `action_type` | string | `classify`, `respond`, `escalate`, `archive`, `skip`, `flag` | ✅ |
| `category` | string | `customer_complaint`, `sales_inquiry`, `technical_support`, `billing`, `partnership`, `internal`, `spam`, `legal`, `press`, `other` | For `classify` |
| `priority` | string | `urgent`, `high`, `medium`, `low`, `ignore` | For `classify` |
| `department` | string | `support`, `sales`, `engineering`, `finance`, `legal`, `marketing`, `executive`, `ignore` | For `classify` |
| `draft_response` | string | Free text email draft | For `respond` |
| `escalation_reason` | string | Free text | For `escalate` |
| `flag_reason` | string | Free text | For `flag` |
| `reasoning` | string | Free text | Optional (encouraged) |

**Priority scale:**
- `urgent` — respond within 1 hour
- `high` — respond within 4 hours
- `medium` — respond within 24 hours
- `low` — can wait
- `ignore` — spam or no action needed

---

## 👁 Observation Space

After each action, the agent receives:

```json
{
  "done": false,
  "reward": 0.72,
  "current_email": {
    "id": "easy_004",
    "sender": "angry.customer@hotmail.com",
    "sender_domain": "hotmail.com",
    "subject": "YOUR SERVICE IS BROKEN - I WANT A REFUND NOW",
    "body": "...",
    "timestamp": "2024-01-15T11:30:00Z",
    "has_attachments": false,
    "thread_length": 1
  },
  "email_index": 3,
  "total_emails": 5,
  "emails_remaining": 2,
  "action_feedback": "[CLASSIFY] Category: customer_complaint vs customer_complaint → 1.00 | Priority: urgent vs urgent → 1.00 | Department: support vs support → 1.00",
  "partial_score": 1.0,
  "emails_processed": 3,
  "correct_classifications": 3,
  "cumulative_score": 0.93,
  "task_instructions": "You are an email triage agent..."
}
```

---

## 📋 Tasks

### Task 1 — Basic Email Triage (Easy)
**5 emails** | Passing score: **0.70**

Clear-cut examples: obvious spam, a sales inquiry from a VP, an internal lunch invite, an angry customer demanding a refund, and a routine billing confirmation. Signals are unambiguous — designed to establish a performance floor.

**Expected baseline score: ~0.85–1.00**

---

### Task 2 — Mixed Inbox with Responses (Medium)
**8 emails** | Passing score: **0.65**

Adds nuance: a patent infringement legal notice, a TechCrunch reporter on deadline, an API rate limit emergency, a partnership inquiry, a billing dispute with attached contract, and a newsletter. Some emails require drafting a response; response quality is graded.

**Expected baseline score: ~0.70–0.85**

---

### Task 3 — Crisis Inbox: High-Stakes Triage (Hard)
**10 emails** | Passing score: **0.60**

Monday morning at a fast-growing SaaS company. The inbox contains:
- An acquisition inquiry from a competitor's CEO
- A security researcher reporting SQL injection + IDOR vulnerabilities
- An internal whistleblower alleging financial misconduct
- A 7-thread complaint from a customer threatening non-renewal
- A formal SEC document request
- An investigative journalist publishing a data breach story in hours
- A $180k/yr customer threatening to churn unless the CTO calls today
- Phishing spam
- A contractor threatening small claims court over 90-day overdue invoice
- A competitor actively recruiting your engineering team

Both classification accuracy and response quality are graded. Misrouting a security disclosure or whistleblower report heavily penalizes the score.

**Expected baseline score: ~0.55–0.75**

---

## 🏆 Reward Function

The reward function provides **dense per-step signal** — the agent learns from every email, not just episode end.

### Per-step reward
```
reward = partial_score × 0.8
```

Where `partial_score` is a weighted composite of:

| Dimension | Weight (Task 1/2/3) | Scoring |
|-----------|-------------------|---------|
| Category accuracy | 0.40 / 0.30 / 0.25 | Exact match = 1.0; semantically close pairs = 0.3–0.5; wrong = 0.0 |
| Priority accuracy | 0.35 / 0.30 / 0.30 | Exact = 1.0; distance-based partial (e.g. high vs urgent = 0.75) |
| Department accuracy | 0.25 / 0.20 / 0.25 | Exact = 1.0; near-miss pairs = 0.4–0.5; wrong = 0.0 |
| Response quality | — / 0.20 / 0.20 | Keyword coverage + professionalism + length |

### Episode bonus
- `+0.1` if final mean score ≥ passing threshold (completion bonus)
- `-0.05` if final mean score < 0.30 (poor performance penalty)

### Penalty signals
- **Skipping an urgent email**: score multiplied by 0.3 (heavy penalty)
- **Responding to spam**: score multiplied by 0.1

### Partial credit examples
| Predicted | Ground Truth | Score |
|-----------|-------------|-------|
| `customer_complaint` | `customer_complaint` | 1.00 |
| `technical_support` | `customer_complaint` | 0.50 |
| `billing` | `customer_complaint` | 0.40 |
| `spam` | `customer_complaint` | 0.00 |
| `urgent` | `urgent` | 1.00 |
| `high` | `urgent` | 0.75 |
| `low` | `urgent` | 0.25 |
| `ignore` | `urgent` | 0.00 |
| `legal` | `executive` | 0.50 |
| `finance` | `support` | 0.00 |

---

## 🚀 Setup & Usage

### Prerequisites
- Python 3.9+
- Docker (for containerized deployment)
- `pip install fastapi uvicorn pydantic requests openai`

### Local development

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/email-triage-openenv
cd email-triage-openenv

pip install -r requirements.txt

# Start server
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health

# Web UI
open http://localhost:8000/web
```

### Docker

```bash
docker build -t email-triage-openenv .
docker run -p 8000:7860 email-triage-openenv

# With custom port
docker run -p 8080:7860 -e PORT=7860 email-triage-openenv
```

### Python API

```python
import requests

BASE = "http://localhost:8000"

# List tasks
tasks = requests.get(f"{BASE}/tasks").json()

# Start episode
result = requests.post(f"{BASE}/reset", json={"task_id": "task_1_easy"}).json()
obs = result["observation"]
print(f"First email: {obs['current_email']['subject']}")

# Take action
step = requests.post(f"{BASE}/step", json={
    "action": {
        "action_type": "classify",
        "category": "spam",
        "priority": "ignore",
        "department": "ignore",
        "reasoning": "Obvious spam with fake discount offer"
    }
}).json()
print(f"Score: {step['observation']['partial_score']}")
print(f"Feedback: {step['observation']['action_feedback']}")

# Get state
state = requests.get(f"{BASE}/state").json()

# Grade episode
grade = requests.post(f"{BASE}/grader", json={
    "task_id": "task_1_easy",
    "action_scores": [1.0, 0.85, 0.72, 1.0, 0.6]
}).json()
print(f"Final: {grade['score']}, Passed: {grade['passed']}")
```

---

## 🤖 Baseline Inference

Run the LLM-based baseline against all 3 tasks:

```bash
# Requires an OpenAI API key
export OPENAI_API_KEY=sk-...
export ENV_BASE_URL=http://localhost:8000

python baseline.py

# Options
python baseline.py --model gpt-4o --task task_3_hard
python baseline.py --model gpt-4o-mini --env-url https://YOUR_SPACE.hf.space
```

The baseline uses:
- `temperature=0.0` for reproducibility
- `seed=42` for environment reset
- Structured JSON prompting with classification rules

### Expected Baseline Scores (gpt-4o-mini)

| Task | Difficulty | Rule-Based Agent | gpt-4o-mini (expected) |
|------|-----------|-----------------|----------------------|
| Task 1 | Easy | ~0.95 | ~0.90–0.95 |
| Task 2 | Medium | ~0.80 | ~0.78–0.88 |
| Task 3 | Hard | ~0.65 | ~0.65–0.78 |

The built-in rule-based baseline runs without any API key via `/baseline`.

When deployed on Hugging Face Spaces, the web UI can also run an LLM baseline
through `/baseline/llm` if you set `OPENAI_API_KEY` as a Space secret. You can
optionally set `OPENAI_BASE_URL` for an OpenAI-compatible provider and
`OPENAI_MODEL` to change the default UI model.

---

## 🌐 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/reset` | POST | Start new episode. Body: `{"task_id": "task_1_easy"}` |
| `/step` | POST | Take action. Body: `{"action": {...}}` |
| `/state` | GET | Current episode metadata |
| `/tasks` | GET | List all tasks + action schema |
| `/grader` | POST | Grade a completed episode |
| `/baseline` | POST | Run built-in rule-based baseline |
| `/baseline/llm` | POST | Run the server-side LLM baseline for one task or all tasks |
| `/web` | GET | Interactive web UI |
| `/docs` | GET | OpenAPI documentation |

---

## 📁 Project Structure

```
email_triage_env/
├── email_triage_env/        # Core package
│   ├── __init__.py
│   ├── models.py            # Typed Action/Observation/State models
│   ├── environment.py       # reset() / step() / state logic
│   ├── graders.py           # Deterministic scoring (0.0–1.0)
│   └── data.py              # 20 synthetic emails + task definitions
├── server/
│   ├── __init__.py
│   └── app.py               # FastAPI server + web UI
├── baseline.py              # LLM inference script
├── openenv.yaml             # OpenEnv manifest
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `7860` | Server port (7860 for HF Spaces) |
| `HOST` | `0.0.0.0` | Bind address |
| `WORKERS` | `2` | Uvicorn worker processes |
| `OPENAI_API_KEY` | unset | Required for `/baseline/llm` in the deployed Space |
| `OPENAI_BASE_URL` | unset | Optional OpenAI-compatible base URL override |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default model shown in the Space UI |

---

## 🧪 Extending the Environment

### Adding new emails

Edit `email_triage_env/data.py` and add to `EASY_EMAILS`, `MEDIUM_EMAILS`, or `HARD_EMAILS`:

```python
{
    "id": "custom_001",
    "sender": "ceo@bigcompany.com",
    "sender_domain": "bigcompany.com",
    "subject": "...",
    "body": "...",
    "timestamp": "2024-01-15T10:00:00Z",
    "has_attachments": False,
    "thread_length": 1,
    "ground_truth": {
        "category": "partnership",
        "priority": "high",
        "department": "sales",
    },
    "expected_response_keywords": ["schedule", "call", "partnership"],
    "response_required": True,
    "tasks": ["medium", "hard"],
}
```

### Creating a custom task

```python
TASKS["task_4_custom"] = {
    "id": "task_4_custom",
    "name": "My Custom Task",
    "difficulty": "medium",
    "description": "...",
    "instructions": "...",
    "emails": MY_EMAIL_LIST,
    "scoring": {
        "category_weight": 0.35,
        "priority_weight": 0.35,
        "department_weight": 0.30,
    },
    "passing_score": 0.65,
}
```

### Custom reward shaping

Override `_compute_reward()` in `environment.py` to customize the reward signal for your training setup.

---

## 📊 Training with TRL + GRPO

This environment is designed to plug directly into TRL's GRPOTrainer:

```python
from envs.email_triage import EmailTriageClient

env = EmailTriageClient(base_url="https://YOUR_SPACE.hf.space")

def rollout_func(trainer, prompts, ...):
    result = env.reset(task_id="task_3_hard")
    obs = result.observation
    
    for turn in range(max_turns):
        if result.done:
            break
        messages = build_messages(obs)
        completion = generate_with_model(trainer, messages)
        action = parse_action_from_completion(completion)
        result = env.step(action)
        obs = result.observation
    
    return build_rollout_data(result)

trainer = GRPOTrainer(
    model=model,
    reward_funcs=[lambda **kw: kw["reward"]],
    rollout_func=rollout_func,
    train_dataset=dataset,
    args=grpo_config,
)
trainer.train()
```

---

## 📜 License

Apache 2.0 — see [LICENSE](LICENSE)
