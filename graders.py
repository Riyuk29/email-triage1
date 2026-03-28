"""
Graders for the Email Triage Environment.
Deterministic scoring 0.0–1.0 with partial credit.
"""

from typing import Dict, Optional, List
from models import TriageAction, ActionType, Category, Priority, Department, GradeResult
from data import EmailRecord


PRIORITY_ORDER = {"urgent": 4, "high": 3, "medium": 2, "low": 1, "ignore": 0}

# Partial credit for semantically-adjacent category pairs
CATEGORY_PARTIAL = {
    ("sales_inquiry", "partnership"): 0.6,
    ("partnership", "sales_inquiry"): 0.6,
    ("customer_complaint", "technical_support"): 0.5,
    ("technical_support", "customer_complaint"): 0.5,
    ("billing", "customer_complaint"): 0.5,
    ("customer_complaint", "billing"): 0.5,
    ("legal", "other"): 0.3,
    ("press", "other"): 0.3,
    ("internal", "other"): 0.4,
    ("legal", "press"): 0.4,
    ("press", "legal"): 0.4,
    ("partnership", "other"): 0.3,
    ("other", "partnership"): 0.3,
}

# Partial credit for routing to adjacent departments
DEPARTMENT_PARTIAL = {
    ("sales", "marketing"): 0.5,
    ("marketing", "sales"): 0.5,
    ("legal", "executive"): 0.6,
    ("executive", "legal"): 0.6,
    ("support", "engineering"): 0.5,
    ("engineering", "support"): 0.5,
    ("sales", "executive"): 0.5,
    ("executive", "sales"): 0.5,
    ("finance", "executive"): 0.4,
    ("executive", "finance"): 0.4,
}


def grade_category(predicted: Optional[str], ground_truth: str) -> float:
    if predicted is None:
        return 0.0
    if predicted == ground_truth:
        return 1.0
    return CATEGORY_PARTIAL.get((predicted, ground_truth), 0.0)


def grade_priority(predicted: Optional[str], ground_truth: str) -> float:
    if predicted is None:
        return 0.0
    if predicted == ground_truth:
        return 1.0
    pred_order = PRIORITY_ORDER.get(predicted, 0)
    true_order = PRIORITY_ORDER.get(ground_truth, 0)
    distance = abs(pred_order - true_order)
    return max(0.0, 1.0 - (distance / 4))


def grade_department(predicted: Optional[str], ground_truth: str) -> float:
    if predicted is None:
        return 0.0
    if predicted == ground_truth:
        return 1.0
    return DEPARTMENT_PARTIAL.get((predicted, ground_truth), 0.0)


def grade_response_quality(
    draft: Optional[str],
    expected_keywords: List[str],
    min_length: int = 30,
) -> float:
    """
    Grade response quality:
      - Empty/too short → 0.0–0.1
      - Professionalism signals (greeting, closing) → up to +0.25
      - Keyword coverage → up to 0.60
      - Floor: any reasonable non-empty response ≥ 0.40
    """
    if not draft:
        return 0.0

    text = draft.lower()

    if len(draft) < min_length:
        return 0.1

    score = 0.0

    # Professionalism: greeting
    if any(g in text for g in ["dear", "hi ", "hello", "thank you for"]):
        score += 0.15

    # Professionalism: closing
    if any(c in text for c in ["regards", "sincerely", "best", "thanks", "cheers"]):
        score += 0.10

    # Length / substance bonus
    if len(draft) > 80:
        score += 0.05

    # Keyword coverage (core content signal)
    if expected_keywords:
        matched = sum(1 for kw in expected_keywords if kw.lower() in text)
        keyword_score = matched / len(expected_keywords)
        score += keyword_score * 0.55
    else:
        # No specific keywords required — general professional response is fine
        score += 0.55

    # Floor: any non-trivial response deserves at least 0.40
    score = max(0.40, score)

    return round(min(1.0, score), 4)


def grade_action(
    action: TriageAction,
    email: EmailRecord,
    task_scoring: Dict[str, float],
) -> GradeResult:
    gt = email["ground_truth"]
    weights = task_scoring
    breakdown: Dict[str, float] = {}
    details_parts: List[str] = []

    if action.action_type == ActionType.CLASSIFY:
        cat_w = weights.get("category_weight", 0.33)
        pri_w = weights.get("priority_weight", 0.33)
        dep_w = weights.get("department_weight", 0.34)

        cat_v = action.category.value if action.category else None
        pri_v = action.priority.value if action.priority else None
        dep_v = action.department.value if action.department else None

        cat_score = grade_category(cat_v, gt["category"])
        pri_score = grade_priority(pri_v, gt["priority"])
        dep_score = grade_department(dep_v, gt["department"])

        breakdown.update({"category": cat_score, "priority": pri_score, "department": dep_score})
        details_parts += [
            f"Category: {cat_v} vs {gt['category']} → {cat_score:.2f}",
            f"Priority: {pri_v} vs {gt['priority']} → {pri_score:.2f}",
            f"Department: {dep_v} vs {gt['department']} → {dep_score:.2f}",
        ]
        total = cat_score * cat_w + pri_score * pri_w + dep_score * dep_w

    elif action.action_type == ActionType.RESPOND:
        resp_score = grade_response_quality(
            action.draft_response,
            email.get("expected_response_keywords", []),
        )
        breakdown["response_quality"] = resp_score
        details_parts.append(f"Response quality → {resp_score:.2f}")
        total = resp_score

    elif action.action_type == ActionType.ESCALATE:
        should = gt["priority"] == "urgent" or gt["department"] in ("legal", "executive")
        total = 0.9 if should else 0.2
        breakdown["escalation"] = total
        details_parts.append(
            f"Escalation {'appropriate' if should else 'unwarranted'} → {total:.2f}"
        )

    elif action.action_type in (ActionType.ARCHIVE, ActionType.SKIP):
        is_low = gt["priority"] in ("low", "ignore")
        is_spam = gt["category"] == "spam"
        total = 0.85 if (is_low or is_spam) else 0.1
        breakdown["archive_appropriate"] = total
        details_parts.append(
            f"Archive/skip {'ok' if (is_low or is_spam) else 'inappropriate'} → {total:.2f}"
        )

    elif action.action_type == ActionType.FLAG:
        total = 0.4
        breakdown["flag"] = total
        details_parts.append(f"Flagged (neutral) → {total:.2f}")

    else:
        total = 0.0
        details_parts.append("Unknown action → 0.0")

    return GradeResult(
        score=round(min(1.0, max(0.0, total)), 4),
        passed=total >= 0.5,
        breakdown=breakdown,
        details=" | ".join(details_parts),
    )


def compute_episode_score(
    action_scores: List[float],
    passing_score: float,
) -> GradeResult:
    if not action_scores:
        return GradeResult(score=0.0, passed=False, details="No actions taken")
    mean = sum(action_scores) / len(action_scores)
    final = round(min(1.0, mean), 4)
    return GradeResult(
        score=final,
        passed=final >= passing_score,
        breakdown={"mean_per_email": mean},
        details=f"Mean score across {len(action_scores)} emails: {mean:.4f}",
    )
