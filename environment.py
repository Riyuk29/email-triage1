"""
Email Triage Environment - Server-Side Logic

Implements the OpenEnv Environment interface:
  reset() → TriageObservation
  step(action) → TriageObservation
  state → TriageState
"""

import uuid
from typing import Optional, List

from models import (
    TriageAction, TriageObservation, TriageState,
    Email, ActionType
)
from data import get_task, EmailRecord
from graders import grade_action, compute_episode_score

# Max classify actions allowed per email before auto-advancing
_MAX_CLASSIFY_PER_EMAIL = 3
# Max respond actions allowed per email before auto-advancing
_MAX_RESPOND_PER_EMAIL = 2


class EmailTriageEnvironment:
    """
    Email triage environment. Simulates a real inbox where an agent
    must classify, prioritize, route, and respond to emails.

    Supports SUPPORTS_CONCURRENT_SESSIONS = True for multi-agent use.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = TriageState()
        self._emails: List[EmailRecord] = []
        self._email_index: int = 0
        self._action_scores: List[float] = []
        self._task_config = {}
        self._done = False
        self._email_classify_count: int = 0  # per-email classify count
        self._email_respond_done: bool = False

    # ─── Public Interface ────────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = "task_1_easy",
        **kwargs,
    ) -> TriageObservation:
        self._task_config = get_task(task_id)
        self._emails = self._task_config["emails"]
        self._email_index = 0
        self._action_scores = []
        self._done = False
        self._email_classify_count = 0
        self._email_respond_done = False

        self._state = TriageState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_id=task_id,
            task_name=self._task_config["name"],
            task_difficulty=self._task_config["difficulty"],
            total_emails=len(self._emails),
            emails_processed=0,
            cumulative_score=0.0,
            max_steps=len(self._emails) * 4,
        )

        return self._make_observation(
            action_feedback="New episode started. Triage the inbox.",
            partial_score=0.0,
        )

    def step(
        self,
        action: TriageAction,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> TriageObservation:
        if self._done:
            return self._make_observation(
                action_feedback="Episode already done. Call reset() to start a new episode.",
                partial_score=0.0,
                force_done=True,
            )

        self._state.step_count += 1

        if not self._emails or self._email_index >= len(self._emails):
            self._done = True
            return self._make_observation(
                action_feedback="No more emails. Episode complete.",
                partial_score=0.0,
                force_done=True,
            )

        current_email = self._emails[self._email_index]
        response_required = current_email.get("response_required", False)

        # ── Grade the action ───────────────────────────────────────────────
        grade = grade_action(
            action=action,
            email=current_email,
            task_scoring=self._task_config["scoring"],
        )
        partial_score = grade.score
        feedback = f"[{action.action_type.value.upper()}] {grade.details}"

        # ── Reward shaping ─────────────────────────────────────────────────
        gt_priority = current_email["ground_truth"]["priority"]
        gt_category = current_email["ground_truth"]["category"]

        if action.action_type in (ActionType.SKIP, ActionType.ARCHIVE):
            if gt_priority == "urgent":
                partial_score *= 0.3
                feedback += " ⚠️ Skipped an URGENT email!"

        if action.action_type == ActionType.RESPOND:
            if gt_category == "spam":
                partial_score *= 0.1
                feedback += " ⚠️ Responded to spam!"
            self._email_respond_done = True

        self._action_scores.append(partial_score)

        # ── Determine whether to advance to next email ─────────────────────
        advance = False

        if action.action_type == ActionType.CLASSIFY:
            self._email_classify_count += 1
            if not response_required:
                # No response needed → advance immediately
                advance = True
            elif self._email_classify_count >= _MAX_CLASSIFY_PER_EMAIL:
                # Agent classified too many times without responding → advance
                advance = True
                feedback += " (auto-advance: max classify attempts reached)"

        elif action.action_type == ActionType.RESPOND:
            # After a response, always advance
            advance = True

        elif action.action_type in (
            ActionType.ESCALATE, ActionType.ARCHIVE,
            ActionType.SKIP, ActionType.FLAG
        ):
            advance = True

        if advance:
            self._email_index += 1
            self._state.emails_processed = min(self._email_index, len(self._emails))
            self._email_classify_count = 0
            self._email_respond_done = False

        # ── Check done ─────────────────────────────────────────────────────
        done = self._email_index >= len(self._emails)
        if done:
            self._done = True

        if self._action_scores:
            self._state.cumulative_score = sum(self._action_scores) / len(self._action_scores)

        return self._make_observation(
            action_feedback=feedback,
            partial_score=partial_score,
            force_done=done,
            reward=self._compute_reward(partial_score, done),
        )

    @property
    def state(self) -> TriageState:
        return self._state

    # ─── Private Helpers ─────────────────────────────────────────────────────

    def _compute_reward(self, partial_score: float, done: bool) -> float:
        step_reward = partial_score * 0.8
        if done and self._action_scores:
            final_mean = sum(self._action_scores) / len(self._action_scores)
            passing = self._task_config.get("passing_score", 0.65)
            if final_mean >= passing:
                step_reward += 0.1
            elif final_mean < 0.3:
                step_reward -= 0.05
        return round(step_reward, 4)

    def _make_observation(
        self,
        action_feedback: str,
        partial_score: float,
        force_done: bool = False,
        reward: Optional[float] = None,
    ) -> TriageObservation:
        done = force_done or self._done
        current_email = None
        if self._emails and self._email_index < len(self._emails):
            raw = self._emails[self._email_index]
            current_email = Email(
                id=raw["id"],
                sender=raw["sender"],
                sender_domain=raw["sender_domain"],
                subject=raw["subject"],
                body=raw["body"],
                timestamp=raw["timestamp"],
                has_attachments=raw.get("has_attachments", False),
                thread_length=raw.get("thread_length", 1),
            )

        return TriageObservation(
            done=done,
            reward=reward,
            current_email=current_email,
            email_index=self._email_index,
            total_emails=len(self._emails),
            emails_remaining=max(0, len(self._emails) - self._email_index),
            action_feedback=action_feedback,
            partial_score=partial_score,
            emails_processed=self._state.emails_processed,
            correct_classifications=sum(1 for s in self._action_scores if s >= 0.75),
            cumulative_score=self._state.cumulative_score,
            task_instructions=self._task_config.get("instructions", ""),
        )
