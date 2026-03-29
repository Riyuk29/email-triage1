#!/usr/bin/env python3
"""
Repo-root deterministic baseline runner expected by submission validators.

This script prefers calling the live environment's `/baseline` endpoint. If no
server is available, it falls back to running the built-in rule baseline
directly in-process, which keeps validation reproducible without external keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests  # type: ignore

DEFAULT_ENV_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")


def _call_remote_baseline(env_url: str, task_id: Optional[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if task_id and task_id != "all":
        payload["task_id"] = task_id

    response = requests.post(
        f"{env_url.rstrip('/')}/baseline",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    summary = result.get("summary", {})
    if not isinstance(result.get("results"), dict) or int(summary.get("tasks_run", 0)) <= 0:
        raise RuntimeError("Remote /baseline response did not include a valid baseline report.")
    return result


def _run_local_baseline(task_id: Optional[str]) -> Dict[str, Any]:
    from server.app import _run_rule_baseline, _task_ids_for_request

    task_ids = _task_ids_for_request(task_id)
    return _run_rule_baseline(task_ids)


def _write_report(result: Dict[str, Any], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)


def main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run the deterministic Email Triage baseline")
    parser.add_argument("--env-url", default=DEFAULT_ENV_URL, help="Environment server URL")
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

    try:
        result = _call_remote_baseline(args.env_url, task_id)
        result["execution_mode"] = "remote"
        result["env_url"] = args.env_url
    except Exception:
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
