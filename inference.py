#!/usr/bin/env python3
"""
Phase-2 inference runner for the Email Triage OpenEnv submission.

Required environment variables for the LLM path:
  API_BASE_URL   - OpenAI-compatible inference endpoint
  MODEL_NAME     - Model identifier for completions
  HF_TOKEN       - API key / Hugging Face token

Optional:
  ENV_BASE_URL      - Environment server URL
  LOCAL_IMAGE_NAME  - Reserved for evaluator compatibility when using local images

Structured stdout format is intentionally minimal because the validator parses
these lines strictly:
  [START] task=<task_id>
  [STEP] step=<n> reward=<reward>
  [END] task=<task_id> score=<score> steps=<n>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
API_KEY = HF_TOKEN or ""
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
IMAGE_NAME = LOCAL_IMAGE_NAME
BENCHMARK = "email-triage"

TASK_IDS = ["task_1_easy", "task_2_medium", "task_3_hard"]
TEMPERATURE = 0.0
MAX_TOKENS = 500
RESET_SEED = 42
DEFAULT_ENV_CANDIDATES = [
    ENV_BASE_URL,
    "http://localhost:7860",
    "http://127.0.0.1:7860",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

SYSTEM_PROMPT = """You are an expert email triage agent for a SaaS company.

For each email you receive, you must output a single JSON action.

Available action types:
- classify: set category, priority, and department
- respond: send a draft_response
- escalate: include escalation_reason
- archive
- skip
- flag: include flag_reason

Categories:
customer_complaint, sales_inquiry, technical_support, billing, partnership,
internal, spam, legal, press, other

Priorities:
urgent, high, medium, low, ignore

Departments:
support, sales, engineering, finance, legal, marketing, executive, ignore

Critical guidance:
- Legal or regulatory notices -> legal / urgent / legal
- Security vulnerabilities -> technical_support / urgent / engineering
- Negative press on deadline -> press / urgent / executive
- VIP churn risk -> customer_complaint / urgent / executive
- Acquisition outreach -> partnership / urgent / executive
- Spam or phishing -> spam / ignore / ignore
- Billing disputes -> billing / high or urgent / finance
- Internal company emails -> internal / low / ignore

Respond only with one valid JSON object and nothing else.
"""


def _stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_str = action.replace("\r", "\\r").replace("\n", "\\n")
    error_str = (error or "none").replace("\r", "\\r").replace("\n", "\\n")
    print(
        f"[STEP] step={step} action={action_str} reward={reward:.4f} done={str(done).lower()} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_json = json.dumps([round(value, 4) for value in rewards], separators=(",", ":"))
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.4f} rewards={rewards_json}",
        flush=True,
    )


def _call_env(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{ENV_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    if method == "POST":
        response = requests.post(url, json=payload or {}, timeout=30)
    else:
        response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_action(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _build_prompt(observation: Dict[str, Any]) -> str:
    email = observation.get("current_email")
    if not email:
        return "No email is currently available."

    parts = [
        "## Email to Triage",
        f"From: {email['sender']} ({email['sender_domain']})",
        f"Subject: {email['subject']}",
        f"Timestamp: {email.get('timestamp', 'unknown')}",
        f"Thread length: {email.get('thread_length', 1)}",
        f"Has attachments: {email.get('has_attachments', False)}",
        "",
        "Body:",
        email["body"],
        "",
        f"Email {observation.get('email_index', 0) + 1} of {observation.get('total_emails', '?')}",
    ]

    feedback = observation.get("action_feedback") or ""
    if feedback and feedback != "New episode started. Triage the inbox.":
        parts.extend(["", f"Previous feedback: {feedback}"])

    parts.extend(["", "Return a single JSON object only."])
    return "\n".join(parts)


def _fallback_action(observation: Dict[str, Any]) -> Dict[str, Any]:
    from models import Email
    from server.app import _make_response_draft, _rule_based_classify

    raw_email = observation.get("current_email") or {}
    email = Email(
        id=raw_email.get("id", ""),
        sender=raw_email.get("sender", ""),
        sender_domain=raw_email.get("sender_domain", ""),
        subject=raw_email.get("subject", ""),
        body=raw_email.get("body", ""),
        timestamp=raw_email.get("timestamp", ""),
        has_attachments=bool(raw_email.get("has_attachments", False)),
        thread_length=int(raw_email.get("thread_length", 1)),
    )

    feedback = (observation.get("action_feedback") or "").lower()
    if "response" in feedback or "draft" in feedback:
        return {
            "action_type": "respond",
            "draft_response": _make_response_draft(email),
            "reasoning": "Fallback response action after classifier feedback indicated a reply is needed.",
        }

    action = _rule_based_classify(email).model_dump(mode="json")
    action["reasoning"] = "Deterministic fallback action."
    return action


def _build_client() -> OpenAI:
    return OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


def _probe_env(base_url: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        response = requests.get(f"{base_url.rstrip('/')}/health", timeout=5)
        response.raise_for_status()
        return True, response.json()
    except Exception:
        return False, None


def _resolve_env_url(preferred_url: str) -> str:
    checked: List[str] = []
    seen = set()

    for candidate in [preferred_url, *DEFAULT_ENV_CANDIDATES]:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        checked.append(candidate)
        ok, _ = _probe_env(candidate)
        if ok:
            return candidate

    raise RuntimeError(f"Could not reach the environment on any known URL: {', '.join(checked)}")


def _discover_task_ids() -> List[str]:
    try:
        payload = _call_env("tasks")
        tasks = payload.get("tasks", [])
        discovered = [str(task.get("id", "")).strip() for task in tasks if str(task.get("id", "")).strip()]
        if discovered:
            return discovered
    except Exception:
        pass
    return TASK_IDS


def _sample_reward(step_result: Dict[str, Any]) -> float:
    if "reward" in step_result and step_result["reward"] is not None:
        try:
            return float(step_result["reward"])
        except (TypeError, ValueError):
            pass

    observation = step_result.get("observation", {})
    reward = observation.get("reward")
    if reward is None:
        return 0.0
    try:
        return float(reward)
    except (TypeError, ValueError):
        return 0.0


def _task_score(task_id: str, action_scores: List[float]) -> float:
    if not action_scores:
        return 0.0

    result = _call_env(
        "grader",
        "POST",
        {
            "task_id": task_id,
            "action_scores": action_scores,
        },
    )
    try:
        return float(result.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


async def _env_call(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await asyncio.to_thread(_call_env, endpoint, method, payload)


def _normalize_action_text(action: Dict[str, Any]) -> str:
    return json.dumps(action, ensure_ascii=True, separators=(",", ":"))


def _success_threshold(task_id: str) -> float:
    from data import TASKS

    return float(TASKS[task_id]["passing_score"])


async def _run_task(client: OpenAI, task_id: str, model_name: str) -> Dict[str, Any]:
    reset = await _env_call(
        "reset",
        "POST",
        {
            "task_id": task_id,
            "seed": RESET_SEED,
        },
    )
    observation = reset.get("observation", {})
    done = bool(reset.get("done", observation.get("done", False)))
    total_emails = int(observation.get("total_emails", 0) or 0)
    max_steps = max(total_emails * 4, 1)
    rewards: List[float] = []
    partial_scores: List[float] = []
    history: List[str] = []
    steps_taken = 0
    step = 0

    log_start(task=task_id, env=BENCHMARK, model=model_name)

    while not done and step < max_steps:
        step = steps_taken + 1
        action = None
        action_text = "hello"
        error: Optional[str] = None

        if HF_TOKEN:
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_prompt(observation)},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=False,
                )
                content = completion.choices[0].message.content or ""
                action = _parse_action(content)
                if action:
                    action_text = _normalize_action_text(action)
            except Exception as exc:
                error = str(exc)
                _stderr(f"LLM call failed on {task_id} step {step}: {exc}")

        if not action:
            action = _fallback_action(observation)
            action_text = _normalize_action_text(action)

        step_result = await _env_call("step", "POST", {"action": action})
        observation = step_result.get("observation", {})
        done = bool(step_result.get("done", observation.get("done", False)))
        partial_score = observation.get("partial_score", 0.0)
        try:
            partial_scores.append(float(partial_score))
        except (TypeError, ValueError):
            partial_scores.append(0.0)

        reward_value = _sample_reward(step_result)
        rewards.append(reward_value)
        steps_taken = step
        log_step(step=step, action=action_text, reward=reward_value, done=done, error=error)
        history.append(f"Step {step}: {action_text} -> reward {reward_value:+.4f}")
        await asyncio.sleep(0.05)

    score = _task_score(task_id, partial_scores)
    success = score >= _success_threshold(task_id)
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task_id": task_id,
        "score": score,
        "steps": steps_taken,
        "reward_trace": rewards,
        "history": history,
        "partial_scores": partial_scores,
        "success": success,
    }


def _write_report(path: str, results: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)


async def main() -> int:
    global ENV_BASE_URL

    parser = argparse.ArgumentParser(description="Run the Email Triage Phase-2 inference baseline")
    parser.add_argument("--env-url", default=ENV_BASE_URL, help="Environment server URL")
    parser.add_argument("--model", default=MODEL_NAME, help="LLM model name")
    parser.add_argument("--task", default="all", help="Task to run")
    parser.add_argument("--output", default="baseline_results.json", help="Output JSON path")
    args = parser.parse_args()

    ENV_BASE_URL = _resolve_env_url(args.env_url)
    client = _build_client()
    available_task_ids = _discover_task_ids()
    task_ids = available_task_ids if args.task == "all" else [args.task]

    if args.task != "all" and args.task not in available_task_ids:
        _stderr(f"Unknown task '{args.task}'. Available tasks: {', '.join(available_task_ids)}")
        return 1

    results: Dict[str, Any] = {
        "api_base_url": API_BASE_URL,
        "model_name": args.model,
        "env_base_url": ENV_BASE_URL,
        "local_image_name": LOCAL_IMAGE_NAME,
        "timestamp": time.time(),
        "results": {},
    }

    try:
        await _env_call("health")
    except Exception as exc:
        _stderr(f"Environment health check failed: {exc}")
        return 1

    for task_id in task_ids:
        results["results"][task_id] = await _run_task(client, task_id, args.model)

    scores = [item["score"] for item in results["results"].values()]
    results["summary"] = {
        "tasks_run": len(task_ids),
        "mean_score": sum(scores) / len(scores) if scores else 0.0,
    }
    _write_report(args.output, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
