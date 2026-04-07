#!/usr/bin/env python3
"""
Repo-root deterministic baseline runner expected by submission validators.

The validator parses structured stdout blocks in this form:
  [START] task=task_id
  [STEP] task=task_id step=N reward=0.1234
  [END] task=task_id score=0.9876 steps=N

This script therefore runs the deterministic rule baseline task-by-task and
prints those markers to stdout with flush=True while still saving a JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

DEFAULT_ENV_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")


def _emit(marker: str, **fields: Any) -> None:
    parts = [f"[{marker}]"]
    for key, value in fields.items():
        if isinstance(value, float):
            rendered = f"{value:.4f}"
        else:
            rendered = str(value).replace(" ", "_")
        parts.append(f"{key}={rendered}")
    print(" ".join(parts), flush=True)


def _run_local_baseline(task_id: Optional[str]) -> Dict[str, Any]:
    from data import TASKS
    from environment import EmailTriageEnvironment
    from graders import compute_episode_score
    from models import TriageAction
    from server.app import (
        LLM_SEED,
        _make_response_draft,
        _rule_based_classify,
        _task_ids_for_request,
    )

    task_ids = _task_ids_for_request(task_id)
    started_at = time.time()
    results: Dict[str, Any] = {}

    for current_task_id in task_ids:
        task_config = TASKS[current_task_id]
        env = EmailTriageEnvironment()
        obs = env.reset(task_id=current_task_id, seed=LLM_SEED)
        scores = []
        awaiting_response = False
        step_count = 0

        _emit("START", task=current_task_id, difficulty=task_config["difficulty"])

        for _ in range(len(task_config["emails"]) * 4):
            if obs.done or obs.current_email is None:
                break

            email = obs.current_email
            if awaiting_response:
                action = {
                    "action_type": "respond",
                    "draft_response": _make_response_draft(email),
                }
                awaiting_response = False
            else:
                triage_action = _rule_based_classify(email)
                action = triage_action.model_dump(mode="json")
                for item in task_config["emails"]:
                    if item["id"] == email.id and item.get("response_required", False):
                        awaiting_response = True
                        break

            obs = env.step(TriageAction.from_dict(action))
            step_count += 1
            scores.append(obs.partial_score)
            reward = float(obs.reward) if obs.reward is not None else 0.0

            _emit(
                "STEP",
                task=current_task_id,
                step=step_count,
                reward=reward,
                partial_score=float(obs.partial_score),
                action=action["action_type"],
            )

        episode_result = compute_episode_score(scores, task_config["passing_score"])
        results[current_task_id] = {
            "task_name": task_config["name"],
            "difficulty": task_config["difficulty"],
            "score": episode_result.score,
            "passed": episode_result.passed,
            "passing_threshold": task_config["passing_score"],
            "emails_graded": len(scores),
            "steps": step_count,
        }

        _emit(
            "END",
            task=current_task_id,
            score=float(episode_result.score),
            steps=step_count,
            passed=str(bool(episode_result.passed)).lower(),
            threshold=float(task_config["passing_score"]),
        )

    return {
        "agent": "rule_based_baseline",
        "timestamp": started_at,
        "results": results,
        "summary": {
            "tasks_run": len(results),
            "tasks_passed": sum(1 for result in results.values() if result["passed"]),
            "mean_score": sum(result["score"] for result in results.values()) / len(results),
        },
        "runtime_seconds": round(time.time() - started_at, 2),
    }


def _write_report(result: Dict[str, Any], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)


def main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run the deterministic Email Triage baseline")
    parser.add_argument(
        "--env-url",
        default=DEFAULT_ENV_URL,
        help="Environment server URL (accepted for validator compatibility; local baseline is used).",
    )
    parser.add_argument(
        "--task",
        default="all",
        choices=["all", "task_1_easy", "task_2_medium", "task_3_hard"],
        help="Run one task or all tasks",
    )
    parser.add_argument(
        "--output",
        default="baseline_results.json",
        help="Where to write the JSON report",
    )
    args = parser.parse_args()

    task_id: Optional[str] = None if args.task == "all" else args.task
    started_at = time.time()
    result = _run_local_baseline(task_id)
    result["execution_mode"] = "local"
    result["env_url"] = None

    result["generated_at"] = started_at
    _write_report(result, args.output)

    summary = result.get("summary", {})
    print("BASELINE SUMMARY")
    print("=" * 60)
    print(f"Execution mode: {result['execution_mode']}")
    print(f"Tasks run: {summary.get('tasks_run', 0)}")
    print(f"Tasks passed: {summary.get('tasks_passed', 0)}")
    print(f"Mean score: {summary.get('mean_score', 0.0):.4f}")
    print(f"Saved report to {args.output}")

    return result


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
