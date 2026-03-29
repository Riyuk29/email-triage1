#!/usr/bin/env python3
"""
Phase 2 evaluation runner for the Email Triage environment.

Runs:
  1. The built-in rule-based baseline
  2. An open-model agent via Hugging Face Inference
  3. Repeat-run variance calculations

Example:
  HF_TOKEN=... python phase2_eval.py --model Qwen/Qwen2.5-72B-Instruct --repeats 3
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from typing import Any, Dict, List

from huggingface_hub.errors import HfHubHTTPError
from huggingface_hub import InferenceClient

from baseline import SYSTEM_PROMPT, build_prompt, parse_action
from data import TASKS
from environment import EmailTriageEnvironment
from graders import compute_episode_score
from models import TriageAction
from server.app import _run_rule_baseline


DEFAULT_OPEN_MODEL = "Qwen/Qwen2.5-72B-Instruct"
DEFAULT_REPEATS = 3
TASK_IDS = list(TASKS.keys())


def _fallback_action() -> Dict[str, Any]:
    return {
        "action_type": "classify",
        "category": "other",
        "priority": "medium",
        "department": "support",
        "reasoning": "Fallback action used because the open-model response was not valid JSON.",
    }


def run_open_model_task(
    client: InferenceClient,
    model: str,
    task_id: str,
    seed: int,
) -> Dict[str, Any]:
    task_config = TASKS[task_id]
    env = EmailTriageEnvironment()
    obs = env.reset(task_id=task_id, seed=seed)
    scores: List[float] = []
    parse_fallbacks = 0
    step_count = 0
    max_steps = len(task_config["emails"]) * 4

    while not obs.done and obs.current_email is not None and step_count < max_steps:
        step_count += 1
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(obs.model_dump())},
        ]

        completion = client.chat_completion(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=500,
            seed=seed,
        )
        output = completion.choices[0].message.content or ""
        action_payload = parse_action(output)
        if action_payload is None:
            action_payload = _fallback_action()
            parse_fallbacks += 1

        try:
            action = TriageAction.from_dict(action_payload)
        except Exception:
            parse_fallbacks += 1
            action = TriageAction.from_dict(_fallback_action())

        obs = env.step(action)
        scores.append(obs.partial_score)

    episode_result = compute_episode_score(scores, task_config["passing_score"])
    return {
        "task_id": task_id,
        "task_name": task_config["name"],
        "difficulty": task_config["difficulty"],
        "score": episode_result.score,
        "passed": episode_result.passed,
        "passing_threshold": task_config["passing_score"],
        "emails_graded": len(scores),
        "steps": step_count,
        "parse_fallbacks": parse_fallbacks,
    }


def summarize_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_task: Dict[str, List[float]] = {}
    passes: Dict[str, int] = {}

    for run in runs:
        for task_id, result in run["results"].items():
            by_task.setdefault(task_id, []).append(float(result["score"]))
            passes[task_id] = passes.get(task_id, 0) + int(bool(result["passed"]))

    task_summary: Dict[str, Dict[str, Any]] = {}
    all_scores: List[float] = []
    for task_id, scores in by_task.items():
        all_scores.extend(scores)
        task_summary[task_id] = {
            "mean_score": round(statistics.fmean(scores), 4),
            "min_score": round(min(scores), 4),
            "max_score": round(max(scores), 4),
            "stddev": round(statistics.pstdev(scores), 6),
            "runs": len(scores),
            "passes": passes[task_id],
        }

    mean_scores = [run["summary"]["mean_score"] for run in runs]
    return {
        "tasks": task_summary,
        "overall": {
            "mean_score": round(statistics.fmean(mean_scores), 4),
            "min_score": round(min(mean_scores), 4),
            "max_score": round(max(mean_scores), 4),
            "stddev": round(statistics.pstdev(mean_scores), 6),
            "runs": len(runs),
        },
    }


def run_open_model_suite(model: str, repeats: int, token: str) -> Dict[str, Any]:
    client = InferenceClient(token=token)
    runs: List[Dict[str, Any]] = []

    for repeat in range(repeats):
        seed = 42 + repeat
        results: Dict[str, Any] = {}
        started_at = time.time()

        for task_id in TASK_IDS:
            results[task_id] = run_open_model_task(client, model, task_id, seed)

        mean_score = statistics.fmean(result["score"] for result in results.values())
        tasks_passed = sum(1 for result in results.values() if result["passed"])
        runs.append(
            {
                "repeat": repeat + 1,
                "seed": seed,
                "model": model,
                "results": results,
                "summary": {
                    "mean_score": round(mean_score, 4),
                    "tasks_passed": tasks_passed,
                    "total_tasks": len(results),
                    "runtime_seconds": round(time.time() - started_at, 2),
                },
            }
        )

    return {
        "agent": "huggingface_open_model",
        "model": model,
        "runs": runs,
        "variance": summarize_runs(runs),
    }


def run_rule_suite(repeats: int) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    for repeat in range(repeats):
        result = _run_rule_baseline(TASK_IDS)
        runs.append(
            {
                "repeat": repeat + 1,
                "seed": 42,
                "results": result["results"],
                "summary": {
                    "mean_score": round(float(result["summary"]["mean_score"]), 4),
                    "tasks_passed": int(result["summary"]["tasks_passed"]),
                    "total_tasks": int(result["summary"]["tasks_run"]),
                    "runtime_seconds": float(result["runtime_seconds"]),
                },
            }
        )

    return {
        "agent": "rule_based_baseline",
        "runs": runs,
        "variance": summarize_runs(runs),
    }


def format_console_summary(report: Dict[str, Any]) -> str:
    lines = ["PHASE 2 SUMMARY", "=" * 60]
    for agent_key in ("rule_baseline", "open_model_agent"):
        if agent_key not in report:
            continue
        section = report[agent_key]
        lines.append(f"{agent_key}: {section.get('model', section['agent'])}")
        overall = section["variance"]["overall"]
        lines.append(
            f"  overall mean={overall['mean_score']:.4f} "
            f"stddev={overall['stddev']:.6f} "
            f"range=[{overall['min_score']:.4f}, {overall['max_score']:.4f}] "
            f"runs={overall['runs']}"
        )
        for task_id, task_summary in section["variance"]["tasks"].items():
            lines.append(
                f"  {task_id}: mean={task_summary['mean_score']:.4f} "
                f"stddev={task_summary['stddev']:.6f} "
                f"passes={task_summary['passes']}/{task_summary['runs']}"
            )
        lines.append("-" * 60)
    return "\n".join(lines)


def main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Phase 2 evaluation runner")
    parser.add_argument("--model", default=DEFAULT_OPEN_MODEL, help="Open model to run through Hugging Face Inference")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS, help="How many repeated runs to execute")
    parser.add_argument("--output", default="phase2_results.json", help="Where to write the JSON report")
    parser.add_argument("--skip-open-model", action="store_true", help="Only run the built-in rule baseline")
    args = parser.parse_args()

    report: Dict[str, Any] = {
        "timestamp": time.time(),
        "repeats": args.repeats,
        "task_ids": TASK_IDS,
    }

    report["rule_baseline"] = run_rule_suite(args.repeats)

    if not args.skip_open_model:
        token = (
            os.getenv("HF_TOKEN")
            or os.getenv("HUGGING_FACE_HUB_TOKEN")
            or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        )
        if not token:
            raise SystemExit(
                "HF_TOKEN (or HUGGING_FACE_HUB_TOKEN / HUGGINGFACEHUB_API_TOKEN) is required for open-model evaluation."
            )
        try:
            report["open_model_agent"] = run_open_model_suite(args.model, args.repeats, token)
        except HfHubHTTPError as exc:
            if "402" in str(exc):
                raise SystemExit(
                    "Open-model evaluation was blocked by Hugging Face Inference credits (HTTP 402). "
                    "Use a token with available provider credits, or point the same evaluator at another funded open-model provider."
                ) from exc
            raise

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(format_console_summary(report))
    print(f"\nSaved report to {args.output}")
    return report


if __name__ == "__main__":
    main()
