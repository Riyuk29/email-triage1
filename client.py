"""
Simple client for the Email Triage OpenEnv server.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

try:
    from .models import TriageAction
except ImportError:
    from models import TriageAction


class EmailTriageEnv:
    """Lightweight HTTP client for interacting with a running Email Triage environment."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/{path.lstrip('/')}",
            params=params or {},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/{path.lstrip('/')}",
            json=payload or {},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()

    def reset(
        self,
        task_id: str = "task_1_easy",
        *,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"task_id": task_id}
        if seed is not None:
            payload["seed"] = seed
        if episode_id:
            payload["episode_id"] = episode_id
        return self._post("/reset", payload)

    def step(self, action: TriageAction | Dict[str, Any], *, episode_id: Optional[str] = None) -> Dict[str, Any]:
        payload_action = action.model_dump() if isinstance(action, TriageAction) else dict(action)
        payload: Dict[str, Any] = {"action": payload_action}
        if episode_id:
            payload["episode_id"] = episode_id
        return self._post("/step", payload)

    def state(self, *, episode_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"episode_id": episode_id} if episode_id else None
        return self._get("/state", params=params)

    def tasks(self) -> Dict[str, Any]:
        return self._get("/tasks")

    def health(self) -> Dict[str, Any]:
        return self._get("/health")
