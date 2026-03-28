#!/usr/bin/env python3
"""
Email Triage OpenEnv - Baseline Inference Script

Uses the OpenAI API (compatible with any OpenAI-compatible endpoint) to run
an LLM agent against all 3 tasks and produce reproducible baseline scores.

Usage:
    python baseline.py [--base-url URL] [--model MODEL] [--task TASK_ID]

Environment variables:
    OPENAI_API_KEY   - Required. Your OpenAI (or compatible) API key.
    OPENAI_BASE_URL  - Optional. Override the API base URL.
    ENV_BASE_URL     - Optional. Override the environment server URL.
                       Defaults to http://localhost:8000

Typical invocation:
    OPENAI_API_KEY=sk-... python baseline.py

Reproducibility:
    - temperature=0.0 for deterministic outputs
    - Fixed task order: easy → medium → hard
    - Seed fixed at 42
"""

import os
import sys
import json
import time
import argparse
import re
import requests  # type: ignore
from typing import Optional, Dict, Any, List

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not found. Run: pip install openai")
    sys.exit(1)


# ─── Configuration ────────────────────────────────────────────────────────────

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)
DEFAULT_MODEL = "gpt-4o-mini"

TASK_IDS = ["task_1_easy", "task_2_medium", "task_3_hard"]

SYSTEM_PROMPT = """You are an expert email triage agent for a SaaS company.

For each email you receive, you must output a JSON action following the schema below.

## Available Action Types
- classify: Assign category, priority, and department
- respond: Draft an email response (use after classify when response is needed)
- escalate: Escalate to human/management (include escalation_reason)
- archive: Archive a processed email
- skip: Skip an email (use sparingly)

## Categories
customer_complaint, sales_inquiry, technical_support, billing, partnership,
internal, spam, legal, press, other

## Priorities
urgent (respond <1hr), high (respond <4hrs), medium (respond <24hrs),
low (can wait), ignore (spam/no action)

## Departments
support, sales, engineering, finance, legal, marketing, executive, ignore

## Critical Rules
- Legal/regulatory emails (SEC, lawsuits, patents): category=legal, priority=urgent, department=legal
- Security vulnerabilities: category=technical_support, priority=urgent, department=engineering
- Press with negative stories: category=press, priority=urgent, department=executive
- VIP customer churn risk: category=customer_complaint, priority=urgent, department=executive
- Acquisition inquiries: category=partnership, priority=urgent, department=executive
- Spam/phishing: category=spam, priority=ignore, department=ignore
- Billing disputes: category=billing, priority=high or urgent, department=finance
- Internal company emails: category=internal, priority=low, department=ignore

## Output Format
Always respond with a single JSON object and nothing else. No markdown, no explanation.

Example:
{
  "action_type": "classify",
  "category": "customer_complaint",
  "priority": "urgent",
  "department": "support",
  "reasoning": "Customer explicitly says service is broken and threatens Twitter post"
}

For response drafts:
{
  "action_type": "respond",
  "draft_response": "Dear [Name],\\n\\nThank you for reaching out...",
  "reasoning": "Urgent complaint requires immediate acknowledgment"
}
"""


def call_env(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
    """Call the environment API."""
    url = f"{ENV_BASE_URL}/{endpoint.lstrip('/')}"
    try:
        if method == "POST":
            resp = requests.post(url, json=data or {}, timeout=30)
        else:
            resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to environment at {ENV_BASE_URL}")
        print("Make sure the server is running: uvicorn app:app --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR calling {endpoint}: {e}")
        return {}


def parse_action(llm_output: str) -> Optional[Dict]:
    """Parse JSON action from LLM output."""
    # Try direct JSON parse
    try:
        return json.loads(llm_output.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try extracting any JSON object
    match = re.search(r'\{[^{}]*\}', llm_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def build_prompt(obs: Dict) -> str:
    """Build the user message from the current observation."""
    email = obs.get("current_email")
    if not email:
        return "No email available."

    parts = [
        f"## Email to Triage",
        f"**From:** {email['sender']} ({email['sender_domain']})",
        f"**Subject:** {email['subject']}",
        f"**Timestamp:** {email.get('timestamp', 'unknown')}",
        f"**Thread length:** {email.get('thread_length', 1)} message(s)",
        f"**Has attachments:** {email.get('has_attachments', False)}",
        f"",
        f"**Body:**",
        f"{email['body']}",
        f"",
        f"---",
        f"Email {obs['email_index'] + 1} of {obs['total_emails']} "
        f"({obs['emails_remaining']} remaining)",
    ]

    if obs.get("action_feedback") and obs["action_feedback"] not in (
        "New episode started. Triage the inbox.", ""
    ):
        parts.append(f"\n**Previous feedback:** {obs['action_feedback']}")

    parts.append(
        "\nOutput your action as a single JSON object."
    )
    return "\n".join(parts)


def run_task(
    client: OpenAI,
    task_id: str,
    model: str,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run the agent on a single task and return results."""
    print(f"\n{'='*60}")
    print(f"Task: {task_id}")

    # Reset environment
    reset_data = call_env("reset", "POST", {"task_id": task_id, "seed": 42})
    obs = reset_data.get("observation", {})
    done = reset_data.get("done", False)

    total_emails = obs.get("total_emails", 0)
    print(f"Emails: {total_emails} | Task: {obs.get('task_instructions', '')[:80]}...")

    episode_scores = []
    step_count = 0
    max_steps = total_emails * 4  # generous limit

    while not done and step_count < max_steps:
        step_count += 1

        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(obs)},
        ]

        # LLM inference
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=0.0,
                max_tokens=500,
                seed=42,
            )
            llm_output = response.choices[0].message.content or ""
        except Exception as e:
            print(f"  [Step {step_count}] LLM error: {e}")
            # Fallback: classify as 'other'
            llm_output = '{"action_type": "classify", "category": "other", "priority": "medium", "department": "support"}'

        # Parse action
        action = parse_action(llm_output)
        if not action:
            if verbose:
                print(f"  [Step {step_count}] Failed to parse action, using fallback")
            action = {
                "action_type": "classify",
                "category": "other",
                "priority": "medium",
                "department": "support",
            }

        # Step environment
        step_data = call_env("step", "POST", {"action": action})
        obs = step_data.get("observation", {})
        done = step_data.get("done", False)

        partial_score = obs.get("partial_score", 0.0)
        episode_scores.append(partial_score)

        if verbose:
            email_idx = obs.get("email_index", step_count)
            feedback = obs.get("action_feedback", "")[:80]
            print(
                f"  [Step {step_count}] {action.get('action_type','?').upper():12s} "
                f"score={partial_score:.3f} | {feedback}"
            )

        time.sleep(0.1)  # Rate limiting

    # Compute final score via grader endpoint
    grader_result = call_env("grader", "POST", {
        "task_id": task_id,
        "action_scores": episode_scores,
    })

    final_score = grader_result.get("score", 0.0)
    passed = grader_result.get("passed", False)
    threshold = grader_result.get("passing_threshold", 0.0)

    print(f"\n  Final score: {final_score:.4f} (threshold: {threshold})")
    print(f"  Result: {'✅ PASSED' if passed else '❌ FAILED'}")

    return {
        "task_id": task_id,
        "task_name": grader_result.get("task_name", task_id),
        "score": final_score,
        "passed": passed,
        "passing_threshold": threshold,
        "steps": step_count,
        "emails_graded": len(episode_scores),
        "mean_per_email": sum(episode_scores) / len(episode_scores) if episode_scores else 0.0,
    }


def main():
    global ENV_BASE_URL
    parser = argparse.ArgumentParser(description="Email Triage OpenEnv Baseline")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM model to use")
    parser.add_argument("--task", choices=TASK_IDS + ["all"], default="all",
                        help="Which task(s) to run")
    parser.add_argument("--env-url", default=ENV_BASE_URL, help="Environment server URL")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    ENV_BASE_URL = args.env_url

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Health check
    health = call_env("health")
    print(f"Environment health: {health}")

    # Init OpenAI client
    client_kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL
    client = OpenAI(**client_kwargs)

    tasks_to_run = TASK_IDS if args.task == "all" else [args.task]

    print(f"\nRunning baseline with model: {args.model}")
    print(f"Tasks: {tasks_to_run}")

    results = {}
    for task_id in tasks_to_run:
        result = run_task(client, task_id, args.model, verbose=args.verbose)
        results[task_id] = result

    # Summary
    print(f"\n{'='*60}")
    print("BASELINE SUMMARY")
    print(f"{'='*60}")
    print(f"{'Task':<35} {'Score':>8} {'Passed':>8}")
    print(f"{'-'*60}")

    total_score = 0.0
    for task_id, result in results.items():
        name = result["task_name"][:35]
        score = result["score"]
        passed = "✅" if result["passed"] else "❌"
        print(f"{name:<35} {score:>8.4f} {passed:>8}")
        total_score += score

    mean_score = total_score / len(results) if results else 0.0
    tasks_passed = sum(1 for r in results.values() if r["passed"])

    print(f"{'-'*60}")
    print(f"{'MEAN':<35} {mean_score:>8.4f} {tasks_passed}/{len(results)} passed")

    # Save results
    output = {
        "model": args.model,
        "timestamp": time.time(),
        "env_url": ENV_BASE_URL,
        "results": results,
        "summary": {
            "mean_score": mean_score,
            "tasks_passed": tasks_passed,
            "total_tasks": len(results),
        },
    }

    with open("baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to baseline_results.json")

    return output


if __name__ == "__main__":
    main()
