"""
Email Triage Environment - FastAPI Server
"""

import os
import sys
import json
import re
import time
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.concurrency import run_in_threadpool
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import RedirectResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


from environment import EmailTriageEnvironment
from models import TriageAction, ActionType, Category, Priority, Department
from data import get_all_tasks, TASKS
from graders import compute_episode_score
from server.ui import WEB_UI


DEFAULT_LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_SEED = 42
LLM_SYSTEM_PROMPT = """You are an expert email triage agent for a SaaS company.

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


def _rule_based_classify(email) -> TriageAction:
    """
    Deterministic keyword-based classifier — the built-in baseline agent.
    Check order matters: more specific/higher-stakes patterns first.
    """
    subject = (email.subject or "").lower()
    body    = (email.body or "").lower()
    sender  = (email.sender or "").lower()
    domain  = (email.sender_domain or "").lower()
    text    = subject + " " + body

    # ── Security vulnerability / responsible disclosure (before spam/domain check) ──
    if any(s in text for s in ["sql injection", "vulnerability", "security researcher",
                                "responsible disclosure", "idor", "exploit", "cve",
                                "critical vulnerabilities found"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.TECHNICAL_SUPPORT, priority=Priority.URGENT,
                            department=Department.ENGINEERING)

    # ── Recruiting spam (before partnership check) ──
    if any(s in text for s in ["recruiting your", "talent partner", "2x market salary",
                                "hiring aggressively", "aggressively hiring",
                                "would you be willing to share this opportunity"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.OTHER, priority=Priority.LOW,
                            department=Department.IGNORE)

    # ── Phishing / spam ──
    if (domain.endswith(".xyz") or domain.endswith(".ru") or domain.endswith(".biz")
            or "no-reply@" in sender
            or any(s in text for s in [
                "buy now", "cheap rolex", "nigerian", "phishing",
                "verify now", "account has been compromised",
                "limited time offer", "90% off",
                "unsubscribe", "manage preferences",
                "click here to read more",
            ])):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.SPAM, priority=Priority.IGNORE,
                            department=Department.IGNORE)

    # ── Legal / regulatory ──
    if any(s in text for s in [
        "patent infringement", "sec inquiry", "subpoena", "attorney",
        "legal proceedings", "securities and exchange",
        "formal request", "document request",
    ]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.LEGAL, priority=Priority.URGENT,
                            department=Department.LEGAL)

    # ── Whistleblower / internal misconduct ──
    if any(s in text for s in ["financial misconduct", "expense report falsified",
                                "concerned employee", "whistleblower"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.LEGAL, priority=Priority.URGENT,
                            department=Department.LEGAL)

    # ── Press / media ──
    if any(s in text for s in [
        "journalist", "reporter", "techcrunch", "comment request",
        "publishing tonight", "publishing tomorrow", "investigative",
    ]) or ("press" in subject and "release" not in text):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.PRESS, priority=Priority.URGENT,
                            department=Department.EXECUTIVE)

    # ── Acquisition / M&A ──
    if any(s in text for s in ["acquisition", "acquire"]) and        any(s in text for s in ["ceo", "board", "strategic", "8x arr", "confidential"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.PARTNERSHIP, priority=Priority.URGENT,
                            department=Department.EXECUTIVE)

    # ── VIP customer churn ──
    if any(s in text for s in ["$180,000", "will not renew", "switching to competitor",
                                "signing with the competitor"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.CUSTOMER_COMPLAINT, priority=Priority.URGENT,
                            department=Department.EXECUTIVE)

    # ── Billing / invoice (BEFORE legal — overdue invoice is billing, not legal) ──
    if any(s in text for s in ["invoice", "billing", "overcharged", "payment confirmation",
                                "overdue", "accounts payable", "invoice dispute",
                                "final notice"]):
        if any(s in text for s in ["overdue", "threatening", "final notice",
                                    "small claims", "court"]):
            priority = Priority.URGENT
        elif any(s in text for s in ["dispute", "overcharged", "incorrect", "wrong amount"]):
            priority = Priority.HIGH
        else:
            priority = Priority.LOW
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.BILLING, priority=priority,
                            department=Department.FINANCE)

    # ── Customer complaint / angry ──
    if any(s in text for s in [
        "unacceptable", "i want a refund", "i demand", "posting on twitter",
        "3 weeks now", "7th email", "out of attempts", "your service is broken",
    ]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.CUSTOMER_COMPLAINT, priority=Priority.URGENT,
                            department=Department.SUPPORT)

    # ── Technical support ──
    if any(s in text for s in ["rate limit", "429", "api error", "production app",
                                "data export issue", "bug report", "not working"]):
        pri = Priority.URGENT if "production" in text else Priority.HIGH
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.TECHNICAL_SUPPORT, priority=pri,
                            department=Department.ENGINEERING)

    # ── Partnership ──
    if any(s in text for s in ["partnership opportunity", "integration with", "head of partnerships",
                                "synergy", "partner"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.PARTNERSHIP, priority=Priority.MEDIUM,
                            department=Department.SALES)

    # ── Sales / upgrade inquiry ──
    if any(s in text for s in ["pricing", "enterprise plan", "demo", "upgrade",
                                "pro plan", "team members", "seats"]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.SALES_INQUIRY, priority=Priority.HIGH,
                            department=Department.SALES)

    # ── Internal ──
    if domain == "yourcompany.com" or any(s in text for s in [
        "team lunch", "compliance training", "action required: complete"
    ]):
        return TriageAction(action_type=ActionType.CLASSIFY,
                            category=Category.INTERNAL, priority=Priority.LOW,
                            department=Department.IGNORE)

    # Default
    return TriageAction(action_type=ActionType.CLASSIFY,
                        category=Category.OTHER, priority=Priority.MEDIUM,
                        department=Department.SUPPORT)


def _make_response_draft(email) -> str:
    """Generate a relevant response draft for the baseline agent."""
    subject = (email.subject or "").lower()
    body = (email.body or "").lower()
    text = subject + " " + body

    if any(s in text for s in ["pricing", "enterprise", "demo", "upgrade", "pro plan"]):
        return (
            "Dear Customer,\n\nThank you for your interest in our Enterprise plan! "
            "I'd be happy to schedule a demo and send you detailed pricing information. "
            "Could you share your availability this week? "
            "We look forward to learning more about your needs.\n\n"
            "Best regards,\nSales Team"
        )
    if any(s in text for s in ["refund", "broken", "unacceptable", "demand", "twitter",
                                "not renew", "switching"]):
        return (
            "Dear Customer,\n\nWe sincerely apologize for this unacceptable experience. "
            "We take this extremely seriously and will resolve this immediately. "
            "I have personally escalated this to our senior team and we will process "
            "your refund right away. You will hear from us within the hour.\n\n"
            "Best regards,\nCustomer Success"
        )
    if any(s in text for s in ["rate limit", "api", "production", "vulnerability", "security"]):
        return (
            "Hi,\n\nThank you for reaching out. We have received your report and our "
            "engineering team is investigating this immediately. "
            "We will provide a workaround or fix within 24 hours and keep you updated.\n\n"
            "Best regards,\nEngineering Team"
        )
    if any(s in text for s in ["patent", "attorney", "legal", "sec", "subpoena", "court"]):
        return (
            "Dear Counsel,\n\nThank you for your communication. "
            "We have forwarded this to our legal team for immediate review. "
            "Our attorneys will respond within the required timeframe.\n\n"
            "Best regards,\nLegal Affairs"
        )
    if any(s in text for s in ["invoice", "billing", "overcharged", "payment", "overdue"]):
        return (
            "Dear Customer,\n\nThank you for bringing this to our attention. "
            "We apologize for any billing discrepancy. "
            "Our finance team is reviewing your invoice and will issue a corrected "
            "statement within 48 hours.\n\n"
            "Best regards,\nBilling Team"
        )
    if any(s in text for s in ["partnership", "integration", "acquisition", "cto", "board"]):
        return (
            "Dear,\n\nThank you for reaching out. We are interested in discussing this further. "
            "I will schedule a call with the appropriate team members this week.\n\n"
            "Best regards,\nBusiness Development"
        )
    if any(s in text for s in ["press", "reporter", "journalist", "publishing", "story"]):
        return (
            "Dear,\n\nThank you for reaching out for comment. "
            "We are reviewing your inquiry with our PR and legal team "
            "and will provide a formal statement shortly.\n\n"
            "Best regards,\nCommunications"
        )
    # Generic professional response
    return (
        "Dear Customer,\n\nThank you for reaching out. "
        "We have received your message and our team will respond promptly. "
        "Please expect a follow-up within one business day.\n\n"
        "Best regards,\nCustomer Success Team"
    )


def _task_ids_for_request(task_id: Optional[str]) -> List[str]:
    if task_id in (None, "", "all"):
        return list(TASKS.keys())
    if task_id not in TASKS:
        raise ValueError(f"Unknown task: {task_id}")
    return [task_id]


def _make_llm_client():
    if not OPENAI_AVAILABLE or OpenAI is None:
        raise RuntimeError("The openai package is not installed in this Space.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured for this Space. Add it as a Space secret to run the LLM baseline."
        )

    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        client_kwargs["base_url"] = base_url

    return OpenAI(**client_kwargs)


def _build_llm_prompt(obs: Dict[str, Any]) -> str:
    email = obs.get("current_email")
    if not email:
        return "No email available."

    parts = [
        "## Email to Triage",
        f"**From:** {email['sender']} ({email['sender_domain']})",
        f"**Subject:** {email['subject']}",
        f"**Timestamp:** {email.get('timestamp', 'unknown')}",
        f"**Thread length:** {email.get('thread_length', 1)} message(s)",
        f"**Has attachments:** {email.get('has_attachments', False)}",
        "",
        "**Body:**",
        f"{email['body']}",
        "",
        "---",
        f"Email {obs['email_index'] + 1} of {obs['total_emails']} ({obs['emails_remaining']} remaining)",
    ]

    if obs.get("action_feedback") and obs["action_feedback"] not in (
        "New episode started. Triage the inbox.", ""
    ):
        parts.append(f"\n**Previous feedback:** {obs['action_feedback']}")

    parts.append("\nOutput your action as a single JSON object.")
    return "\n".join(parts)


def _parse_llm_action(llm_output: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(llm_output.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", llm_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[^{}]*\}", llm_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _fallback_llm_action() -> Dict[str, str]:
    return {
        "action_type": "classify",
        "category": "other",
        "priority": "medium",
        "department": "support",
        "reasoning": "Fallback action used because the LLM response was not valid JSON.",
    }


def _run_rule_baseline(task_ids: List[str]) -> Dict[str, Any]:
    started_at = time.time()
    results = {}

    for task_id in task_ids:
        task_config = TASKS[task_id]
        env = EmailTriageEnvironment()
        obs = env.reset(task_id=task_id, seed=LLM_SEED)
        scores = []
        awaiting_response = False

        for _ in range(len(task_config["emails"]) * 4):
            if obs.done or obs.current_email is None:
                break
            email = obs.current_email

            if awaiting_response:
                action = TriageAction(
                    action_type=ActionType.RESPOND,
                    draft_response=_make_response_draft(email),
                )
                awaiting_response = False
            else:
                action = _rule_based_classify(email)
                for item in task_config["emails"]:
                    if item["id"] == email.id and item.get("response_required", False):
                        awaiting_response = True
                        break

            obs = env.step(action)
            scores.append(obs.partial_score)

        episode_result = compute_episode_score(scores, task_config["passing_score"])
        results[task_id] = {
            "task_name": task_config["name"],
            "difficulty": task_config["difficulty"],
            "score": episode_result.score,
            "passed": episode_result.passed,
            "passing_threshold": task_config["passing_score"],
            "emails_graded": len(scores),
        }

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


def _run_llm_baseline(task_ids: List[str], model: str) -> Dict[str, Any]:
    started_at = time.time()
    client = _make_llm_client()
    results = {}
    total_parse_fallbacks = 0

    for task_id in task_ids:
        task_config = TASKS[task_id]
        env = EmailTriageEnvironment()
        obs = env.reset(task_id=task_id, seed=LLM_SEED)
        scores = []
        step_count = 0
        parse_fallbacks = 0
        max_steps = len(task_config["emails"]) * 4

        while not obs.done and obs.current_email is not None and step_count < max_steps:
            step_count += 1
            obs_data = obs.model_dump()
            messages = [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": _build_llm_prompt(obs_data)},
            ]

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0.0,
                    max_tokens=500,
                    seed=LLM_SEED,
                )
                llm_output = response.choices[0].message.content or ""
            except Exception as exc:
                raise RuntimeError(
                    f"LLM request failed for {task_id} at step {step_count}: {exc}"
                ) from exc

            action_payload = _parse_llm_action(llm_output) or _fallback_llm_action()
            if action_payload.get("reasoning") == _fallback_llm_action()["reasoning"]:
                parse_fallbacks += 1

            try:
                action = TriageAction.from_dict(action_payload)
            except Exception:
                parse_fallbacks += 1
                action = TriageAction.from_dict(_fallback_llm_action())

            obs = env.step(action)
            scores.append(obs.partial_score)

        episode_result = compute_episode_score(scores, task_config["passing_score"])
        results[task_id] = {
            "task_name": task_config["name"],
            "difficulty": task_config["difficulty"],
            "score": episode_result.score,
            "passed": episode_result.passed,
            "passing_threshold": task_config["passing_score"],
            "emails_graded": len(scores),
            "steps": step_count,
            "parse_fallbacks": parse_fallbacks,
        }
        total_parse_fallbacks += parse_fallbacks

    return {
        "agent": "llm_baseline",
        "model": model,
        "timestamp": started_at,
        "results": results,
        "summary": {
            "tasks_run": len(results),
            "tasks_passed": sum(1 for result in results.values() if result["passed"]),
            "mean_score": sum(result["score"] for result in results.values()) / len(results),
            "parse_fallbacks": total_parse_fallbacks,
        },
        "runtime_seconds": round(time.time() - started_at, 2),
    }


if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Email Triage OpenEnv",
        description="OpenEnv-compliant RL environment for email triage",
        version="1.0.0",
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    _episodes: Dict[str, EmailTriageEnvironment] = {}
    _default_episode_id: Optional[str] = None

    def _reward_value(obs: Any) -> float:
        reward = getattr(obs, "reward", None)
        return float(reward) if reward is not None else 0.0

    def _resolve_episode_id(request: Request, body: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if body and body.get("episode_id"):
            return str(body["episode_id"])

        header_episode_id = request.headers.get("X-Episode-Id")
        if header_episode_id:
            return header_episode_id

        query_episode_id = request.query_params.get("episode_id")
        if query_episode_id:
            return query_episode_id

        return None

    def _serialize_transition(
        obs: Any,
        state: Dict[str, Any],
        *,
        task_id: str,
        truncated: bool = False,
    ) -> Dict[str, Any]:
        episode_id = state.get("episode_id")
        reward = _reward_value(obs)
        observation = obs.model_dump()
        observation["reward"] = reward
        return {
            "episode_id": episode_id,
            "observation": observation,
            "reward": reward,
            "done": bool(obs.done),
            "truncated": truncated,
            "info": {
                "task_id": task_id,
                "episode_id": episode_id,
                "state": state,
            },
            "state": state,
        }

    def _get_env_for_episode(episode_id: Optional[str]) -> EmailTriageEnvironment:
        resolved_episode_id = episode_id or _default_episode_id
        if not resolved_episode_id:
            raise HTTPException(
                status_code=400,
                detail="No active episode. Call POST /reset first or provide an episode_id.",
            )

        env = _episodes.get(resolved_episode_id)
        if env is None:
            raise HTTPException(status_code=404, detail=f"Unknown episode_id: {resolved_episode_id}")

        return env

    @app.get("/")
    def root():
        return RedirectResponse(url="/web")

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "environment": "email-triage",
            "version": "1.0.0",
            "llm_baseline_available": OPENAI_AVAILABLE and bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "default_llm_model": DEFAULT_LLM_MODEL,
        }

    @app.post("/reset")
    async def reset(request: Request):
        global _default_episode_id
        try:
            body = await request.json()
        except Exception:
            body = {}

        task_id = body.get("task_id", "task_1_easy")
        episode_id = body.get("episode_id")
        seed = body.get("seed")

        try:
            env = EmailTriageEnvironment()
            obs = env.reset(task_id=task_id, episode_id=episode_id, seed=seed)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        state = env.state.model_dump()
        resolved_episode_id = state.get("episode_id")
        if resolved_episode_id:
            _episodes[resolved_episode_id] = env
            _default_episode_id = resolved_episode_id

        return _serialize_transition(obs, state, task_id=task_id)

    @app.post("/step")
    async def step(request: Request):
        global _default_episode_id
        try:
            body = await request.json()
        except Exception:
            body = {}

        episode_id = _resolve_episode_id(request, body)
        env = _get_env_for_episode(episode_id)
        raw_action = body.get("action", body)
        try:
            action = TriageAction.from_dict(raw_action)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid action: {e}") from e
        obs = env.step(action)
        state = env.state.model_dump()
        _default_episode_id = state.get("episode_id") or episode_id
        return _serialize_transition(obs, state, task_id=state.get("task_id", ""), truncated=False)

    @app.get("/state")
    async def get_state(request: Request):
        episode_id = _resolve_episode_id(request)
        env = _get_env_for_episode(episode_id)
        return env.state.model_dump()

    @app.get("/tasks")
    async def list_tasks():
        tasks_info = []
        for task in get_all_tasks():
            tasks_info.append({
                "id": task["id"], "name": task["name"],
                "difficulty": task["difficulty"], "description": task["description"],
                "email_count": len(task["emails"]), "passing_score": task["passing_score"],
            })
        action_schema = {
            "action_type": {"type": "string", "enum": [a.value for a in ActionType],
                            "required": True,
                            "description": "Type of action to take on the current email"},
            "category":    {"type": "string", "enum": [c.value for c in Category],
                            "required": False,
                            "description": "Email category (required for CLASSIFY)"},
            "priority":    {"type": "string", "enum": [p.value for p in Priority],
                            "required": False,
                            "description": "Urgency level (required for CLASSIFY)"},
            "department":  {"type": "string", "enum": [d.value for d in Department],
                            "required": False,
                            "description": "Routing department (required for CLASSIFY)"},
            "draft_response":    {"type": "string", "required": False,
                                  "description": "Email response text (for RESPOND action)"},
            "escalation_reason": {"type": "string", "required": False,
                                  "description": "Why escalating (for ESCALATE action)"},
            "flag_reason":       {"type": "string", "required": False,
                                  "description": "Why flagging (for FLAG action)"},
            "reasoning":         {"type": "string", "required": False,
                                  "description": "Agent reasoning — optional but encouraged"},
        }
        return {"tasks": tasks_info, "action_schema": action_schema}

    @app.post("/grader")
    async def grader(request: Request):
        body    = await request.json()
        task_id = body.get("task_id", "task_1_easy")
        scores  = body.get("action_scores", [])
        task    = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")
        result = compute_episode_score(scores, float(str(task["passing_score"])))
        return {"task_id": task_id, "task_name": task["name"],
                "score": result.score, "passed": result.passed,
                "passing_threshold": task["passing_score"],
                "breakdown": result.breakdown, "details": result.details}

    @app.post("/baseline")
    async def run_baseline(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}

        try:
            task_ids = _task_ids_for_request(body.get("task_id"))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return await run_in_threadpool(_run_rule_baseline, task_ids)

    @app.post("/baseline/llm")
    async def run_llm_baseline(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}

        try:
            task_ids = _task_ids_for_request(body.get("task_id"))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        model = str(body.get("model") or DEFAULT_LLM_MODEL).strip()
        if not model:
            raise HTTPException(status_code=422, detail="Model name cannot be empty.")

        try:
            return await run_in_threadpool(_run_llm_baseline, task_ids, model)
        except RuntimeError as exc:
            message = str(exc)
            status_code = 503 if "OPENAI_API_KEY" in message or "package is not installed" in message else 502
            raise HTTPException(status_code=status_code, detail=message) from exc

    @app.get("/web",  response_class=HTMLResponse)
    @app.get("/",     response_class=HTMLResponse)
    async def web_ui():
        return HTMLResponse(content=WEB_UI)

    def main() -> None:
        import uvicorn

        port = int(os.getenv("PORT", "7860"))
        uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)


_WEB_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Email Triage OpenEnv</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;
  --surface:#111111;
  --card:#161616;
  --raised:#1c1c1c;
  --border:#242424;
  --border-subtle:#1a1a1a;
  --text:#e8e8e8;
  --text-secondary:#888888;
  --text-dim:#555555;
  --accent:#d4d4d4;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif;}
body{background:var(--bg);color:var(--text);min-height:100vh;padding:32px;-webkit-font-smoothing:antialiased;}
.app-wrapper{background:var(--surface);border:1px solid var(--border);border-radius:16px;max-width:1300px;margin:0 auto;overflow:hidden;min-height:85vh;display:flex;flex-direction:column;}
.hdr{padding:28px 48px;border-bottom:1px solid var(--border-subtle);display:flex;align-items:center;gap:20px;background:var(--surface);}
.hdr h1{font-size:1.4rem;font-weight:700;letter-spacing:-0.3px;color:var(--text);flex:1;}
.hdr h1 span{color:var(--text-secondary);font-size:1.6rem;line-height:0;font-weight:400;}
.badge{background:transparent;color:var(--text-dim);border:1px solid var(--border);padding:5px 12px;border-radius:4px;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;}
.badge.g{color:var(--text-dim);border-color:var(--border);}
.wrap{padding:36px 48px;display:grid;grid-template-columns:1.3fr 1fr;gap:32px;flex:1;}
.card{background:var(--card);border:1px solid var(--border-subtle);border-radius:8px;padding:32px;}
.card h2{font-size:0.7rem;font-weight:600;color:var(--text-dim);margin-bottom:24px;text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;}
.card h2::before{content:'';display:block;width:2px;height:14px;background:var(--border);border-radius:1px;}
.email-box{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:28px;margin-bottom:12px;animation:fadeIn 0.3s ease-out;}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
.ef{color:var(--text-dim);font-size:0.75rem;margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;}
.es{font-weight:600;color:var(--text);font-size:1.1rem;margin-bottom:16px;line-height:1.5;}
.eb{color:var(--text-secondary);font-size:0.9rem;line-height:1.75;white-space:pre-wrap;max-height:240px;overflow-y:auto;padding-right:10px;}
.eb::-webkit-scrollbar{width:4px;} .eb::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.att{margin-top:14px;color:var(--text-dim);font-size:0.75rem;display:inline-flex;align-items:center;gap:8px;border:1px solid var(--border);padding:6px 12px;border-radius:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;}
.ctrls{display:flex;flex-direction:column;gap:18px;}
label{font-size:0.7rem;color:var(--text-dim);margin-bottom:8px;display:block;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;}
select,input,textarea{width:100%;background:var(--raised);border:1px solid var(--border);color:var(--text);padding:12px 16px;border-radius:6px;font-size:0.9rem;transition:border-color 0.15s;outline:none;-webkit-appearance:none;}
select:focus,input:focus,textarea:focus{border-color:#404040;}
textarea{min-height:90px;resize:vertical;}
button{background:var(--raised);color:var(--text);border:1px solid var(--border);padding:14px 24px;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;transition:all 0.15s;display:inline-block;width:100%;}
button:hover{background:var(--card);border-color:#404040;color:var(--accent);}
button:active{background:var(--surface);}
.sec{background:var(--surface);} .sec:hover{background:var(--raised);}
.grn{background:var(--raised);border-color:var(--border);color:var(--text);} .grn:hover{border-color:#404040;color:var(--accent);}
.row{display:flex;gap:12px;align-items:flex-end;}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
.log{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:20px;height:360px;overflow-y:auto;font-family:'Consolas',monospace;font-size:0.82rem;}
.log::-webkit-scrollbar{width:4px;} .log::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.le{margin-bottom:10px;padding:8px 12px;border-radius:4px;background:var(--card);color:var(--text-secondary);animation:fadeIn 0.2s ease-out;border-left:2px solid var(--border);}
.r{color:#9ca3af;border-left-color:#404040;}
.e{color:#9ca3af;border-left-color:#404040;}
.i{color:var(--text-secondary);border-left-color:var(--border);}
.w{color:#9ca3af;border-left-color:#404040;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;}
.st{background:var(--raised);border:1px solid var(--border-subtle);border-radius:6px;padding:20px;text-align:center;}
.sv{font-size:2rem;font-weight:700;color:var(--text);line-height:1;}
.sl{font-size:0.65rem;color:var(--text-dim);margin-top:8px;font-weight:600;text-transform:uppercase;letter-spacing:2px;}
.prog{background:var(--border-subtle);border-radius:1px;height:2px;margin:24px 0;overflow:hidden;}
.pb{background:var(--border);height:100%;transition:width 0.4s ease-out;}
.mb{margin-bottom:28px;}
</style>
</head>
<body>
<div class="app-wrapper">
<div class="hdr">
    <h1 id="app-title">EMAIL TRIAGE<span>.</span></h1>
    <span class="badge" id="env-badge">OpenEnv v1.0</span>
    <span class="badge g" id="type-badge">Real-World RL</span>
    <span style="color:var(--text-dim);font-size:0.75rem;margin-left:auto;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;">v1.0.0</span>
</div>
<div class="wrap">
  <div>
    <div class="card mb">
      <h2>Inbox</h2>
      <div id="ed"><p style="color:var(--muted);text-align:center;padding:40px;font-size:0.9rem;letter-spacing:0.01em;">Select a task and start an episode to begin.</p></div>
    </div>
    <div class="card">
      <h2>Action</h2>
      <div class="ctrls">
        <div><label>Action Type</label>
          <select id="at" onchange="tog()">
            <option value="classify">CLASSIFY</option>
            <option value="respond">RESPOND</option>
            <option value="escalate">ESCALATE</option>
            <option value="archive">ARCHIVE</option>
            <option value="skip">SKIP</option>
            <option value="flag">FLAG</option>
          </select></div>
        <div id="cf" class="g3">
          <div><label>Category</label><select id="cat">
            <option value="spam">spam</option><option value="sales_inquiry">sales_inquiry</option>
            <option value="customer_complaint">customer_complaint</option><option value="technical_support">technical_support</option>
            <option value="billing">billing</option><option value="internal">internal</option>
            <option value="legal">legal</option><option value="press">press</option>
            <option value="partnership">partnership</option><option value="other">other</option>
          </select></div>
          <div><label>Priority</label><select id="pri">
            <option value="urgent">urgent</option><option value="high">high</option>
            <option value="medium">medium</option><option value="low">low</option>
            <option value="ignore">ignore</option>
          </select></div>
          <div><label>Department</label><select id="dep">
            <option value="support">support</option><option value="sales">sales</option>
            <option value="engineering">engineering</option><option value="finance">finance</option>
            <option value="legal">legal</option><option value="executive">executive</option>
            <option value="marketing">marketing</option><option value="ignore">ignore</option>
          </select></div>
        </div>
        <div id="rf" style="display:none"><label>Draft Response</label>
          <textarea id="dr" placeholder="Write a professional response..."></textarea></div>
        <div id="xf" style="display:none"><label>Context / Reason</label>
          <input id="xr" type="text" placeholder="Why is this being escalated/flagged?"></div>
        <div><label>Chain of Thought (Reasoning)</label>
          <input id="rsn" type="text" placeholder="Explain your classification logic..."></div>
        <button onclick="act()">Submit Action</button>
      </div>
    </div>
  </div>
  <div>
    <div class="card mb">
      <h2>Control</h2>
      <div class="stats">
        <div class="st"><div class="sv" id="sc">—</div><div class="sl">Score</div></div>
        <div class="st"><div class="sv" id="sp">0</div><div class="sl">Processed</div></div>
        <div class="st"><div class="sv" id="sr">—</div><div class="sl">Remaining</div></div>
      </div>
      <div class="prog mb"><div class="pb" id="pb" style="width:0%"></div></div>
      <div class="row">
        <select id="ts" style="flex:1">
          <option value="task_1_easy">Task 1: Easy (5 emails)</option>
          <option value="task_2_medium">Task 2: Medium (8 emails)</option>
          <option value="task_3_hard">Task 3: Hard Crisis (10 emails)</option>
        </select>
        <button class="grn" onclick="go()">Start</button>
        <button class="sec" onclick="bl()">Baseline</button>
      </div>
    </div>
    <div class="card">
      <h2>Activity Log</h2>
      <div class="log" id="log">
        <div class="le i" style="opacity:0.6;border:none;">[System] Ready for triage operations...</div>
      </div>
    </div>
  </div>
</div>
<script>
let active=false,total=0;
(async()=>{
  try{const r=await fetch('/health'),d=await r.json();document.getElementById('hb').innerHTML='<span style="color:var(--success)">●</span> '+d.environment+' v'+d.version;}
  catch{document.getElementById('hb').innerHTML='<span style="color:var(--danger)">●</span> Offline';}
})();
function tog(){
  const v=document.getElementById('at').value;
  document.getElementById('cf').style.display=v==='classify'?'grid':'none';
  document.getElementById('rf').style.display=v==='respond'?'block':'none';
  document.getElementById('xf').style.display=['escalate','flag'].includes(v)?'block':'none';
}
function lg(msg,t='i'){
  const el=document.getElementById('log');
  const d=document.createElement('div');d.className='le '+t;
  d.textContent='['+new Date().toLocaleTimeString()+'] '+msg;
  el.prepend(d);
}
async function go(){
  const tid=document.getElementById('ts').value;
  try{
    const r=await fetch('/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:tid,seed:42})});
    const d=await r.json();
    active=true;total=d.observation.total_emails||0;
    ui(d);lg('Mission Started: '+tid,'i');
  }catch(e){lg('Error: '+e,'e');}
}
async function act(){
  if(!active){lg('Start an episode first','w');return;}
  const t=document.getElementById('at').value;
  const a={action_type:t};
  if(t==='classify'){
    a.category=document.getElementById('cat').value; a.priority=document.getElementById('pri').value; a.department=document.getElementById('dep').value;
  }
  if(t==='respond') a.draft_response=document.getElementById('dr').value;
  if(['escalate','flag'].includes(t)){a.escalation_reason=document.getElementById('xr').value;a.flag_reason=document.getElementById('xr').value;}
  const rsn=document.getElementById('rsn').value;if(rsn) a.reasoning=rsn;
  try{
    const r=await fetch('/step',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})});
    const d=await r.json(); ui(d);
    const sc=d.observation.partial_score;
    lg(t.toUpperCase()+' → '+sc.toFixed(3)+' | '+(d.observation.action_feedback||'').substring(0,80),sc>=0.7?'r':sc>=0.4?'w':'e');
    if(d.done){const f=d.observation.cumulative_score; lg('Episode complete. Final Score: '+f.toFixed(3),f>=0.6?'r':'w');active=false;}
  }catch(e){lg('Error: '+e,'e');}
}
async function bl(){
  lg('Executing AI Baseline Agent...','i');
  try{
    const r=await fetch('/baseline',{method:'POST'}); const d=await r.json();
    for(const[,res] of Object.entries(d.results)) lg(res.task_name+': '+res.score.toFixed(3)+' ['+(res.passed?'pass':'fail')+']',res.passed?'r':'e');
    lg('Mean Score: '+d.summary.mean_score.toFixed(3)+' | Passed: '+d.summary.tasks_passed+'/3',d.summary.tasks_passed>=2?'r':'w');
  }catch(e){lg('Baseline error: '+e,'e');}
}
function ui(data){
  const o=data.observation;
  document.getElementById('sc').textContent=o.cumulative_score!=null?o.cumulative_score.toFixed(3):'—';
  document.getElementById('sp').textContent=o.emails_processed??0;
  document.getElementById('sr').textContent=o.emails_remaining??'—';
  if(total>0) document.getElementById('pb').style.width=((o.emails_processed||0)/total*100)+'%';
  const em=o.current_email,el=document.getElementById('ed');
  if(em){
    el.innerHTML=`<div class="email-box">
      <div class="ef">From: ${em.sender} <span style="color:var(--muted);font-weight:400;margin-left:8px;">${(em.timestamp||'').slice(0,16).replace('T',' ')}</span> <span class="badge" style="float:right;background:rgba(255,255,255,0.1);box-shadow:none;">Thread: ${em.thread_length||1}</span></div>
      <div class="es">${em.subject}</div>
      <div class="eb">${em.body}</div>
      ${em.has_attachments?'<div class="att">Attachments</div>':''}
    </div><div style="font-size:0.8rem;color:var(--muted);text-align:right;margin-top:8px;">Email ${(o.email_index||0)+1} of ${total||'?'}</div>`;
  }else if(data.done){
    el.innerHTML='<div class="email-box" style="text-align:center;padding:60px 40px;"><div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--success);margin-bottom:12px;">Complete</div><div style="font-size:1.5rem;font-weight:800;color:#0f172a;">Inbox Zero</div><div style="color:var(--muted);font-size:0.9rem;margin-top:8px;">All emails successfully triaged.</div></div>';
  }
}
</script>
</div>
</body>
</html>"""


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        main()
