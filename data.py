"""
Synthetic Email Dataset for the Email Triage Environment.

Each email has:
  - The email itself (sender, subject, body)
  - Ground-truth labels (category, priority, department)
  - A draft response template (for response quality grading)
  - Task tags indicating which tasks include this email
"""

from typing import List, Dict, Any

# ─── Type alias ──────────────────────────────────────────────────────────────
EmailRecord = Dict[str, Any]

# ─── EASY TASK (Task 1) ──────────────────────────────────────────────────────
# 5 very clear-cut emails with obvious categories and priorities

EASY_EMAILS: List[EmailRecord] = [
    {
        "id": "easy_001",
        "sender": "john.doe@gmail.com",
        "sender_domain": "gmail.com",
        "subject": "BUY NOW - Cheap Rolex Watches 90% OFF!!!",
        "body": (
            "Dear Friend,\n\nCongratulations! You have been selected for an exclusive deal.\n"
            "Visit http://totally-not-a-scam.ru/watches to claim your FREE Rolex watch.\n"
            "Limited time offer. Act NOW!\n\nBest,\nNigerian Prince"
        ),
        "timestamp": "2024-01-15T09:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "spam",
            "priority": "ignore",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["easy", "medium"],
    },
    {
        "id": "easy_002",
        "sender": "sarah.johnson@acmecorp.com",
        "sender_domain": "acmecorp.com",
        "subject": "Interested in your Enterprise plan - pricing question",
        "body": (
            "Hi,\n\nMy name is Sarah Johnson, VP of Engineering at Acme Corp. "
            "We currently have 200 engineers and are looking for a solution like yours.\n\n"
            "Could you send me pricing for your Enterprise plan? "
            "We're evaluating vendors this month and would like to schedule a demo.\n\n"
            "Best,\nSarah\n+1 (555) 234-5678"
        ),
        "timestamp": "2024-01-15T10:30:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "sales_inquiry",
            "priority": "high",
            "department": "sales",
        },
        "expected_response_keywords": ["pricing", "demo", "enterprise", "schedule"],
        "response_required": True,
        "tasks": ["easy", "medium", "hard"],
    },
    {
        "id": "easy_003",
        "sender": "mike.chen@yourcompany.com",
        "sender_domain": "yourcompany.com",
        "subject": "Team lunch Friday - pizza or sushi?",
        "body": (
            "Hey everyone,\n\nPlanning the team lunch for Friday. "
            "Vote: pizza or sushi?\n\nMike"
        ),
        "timestamp": "2024-01-15T11:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "internal",
            "priority": "low",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["easy"],
    },
    {
        "id": "easy_004",
        "sender": "angry.customer@hotmail.com",
        "sender_domain": "hotmail.com",
        "subject": "YOUR SERVICE IS BROKEN - I WANT A REFUND NOW",
        "body": (
            "I've been a customer for 3 years and this is UNACCEPTABLE.\n\n"
            "Your app has been down for 2 days and I'm losing business because of it. "
            "I demand a full refund and an explanation. "
            "This is the THIRD time this has happened.\n\n"
            "If I don't hear back within the hour I'm posting on Twitter.\n\n"
            "- Frustrated Customer"
        ),
        "timestamp": "2024-01-15T11:30:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "customer_complaint",
            "priority": "urgent",
            "department": "support",
        },
        "expected_response_keywords": ["apologize", "sorry", "refund", "resolve", "immediate"],
        "response_required": True,
        "tasks": ["easy", "medium", "hard"],
    },
    {
        "id": "easy_005",
        "sender": "billing@stripe.com",
        "sender_domain": "stripe.com",
        "subject": "Invoice #INV-2024-0115 - Payment Confirmation",
        "body": (
            "Your payment of $2,450.00 has been processed successfully.\n\n"
            "Invoice: INV-2024-0115\nDate: January 15, 2024\nAmount: $2,450.00\n"
            "Status: Paid\n\nThank you for your business."
        ),
        "timestamp": "2024-01-15T12:00:00Z",
        "has_attachments": True,
        "thread_length": 1,
        "ground_truth": {
            "category": "billing",
            "priority": "low",
            "department": "finance",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["easy", "medium"],
    },
]

# ─── MEDIUM TASK (Task 2) ─────────────────────────────────────────────────────
# 8 emails with more ambiguity — overlapping categories, nuanced priority

MEDIUM_EMAILS: List[EmailRecord] = [
    # Re-use some easy ones + add ambiguous cases
    {
        "id": "med_001",
        "sender": "legal@bigfirm.com",
        "sender_domain": "bigfirm.com",
        "subject": "Notice of Potential Patent Infringement - Response Required",
        "body": (
            "Dear Sir/Madam,\n\n"
            "We represent TechPatents LLC. It has come to our attention that your product "
            "may infringe on US Patent #9,876,543 ('System for Processing Data').\n\n"
            "We request a response within 14 days confirming your intent to either "
            "license the technology or cease use.\n\n"
            "Failure to respond may result in legal proceedings.\n\n"
            "Regards,\nAttorney B. Smith, Esq."
        ),
        "timestamp": "2024-01-15T08:00:00Z",
        "has_attachments": True,
        "thread_length": 1,
        "ground_truth": {
            "category": "legal",
            "priority": "urgent",
            "department": "legal",
        },
        "expected_response_keywords": ["legal", "attorney", "review", "respond"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
    {
        "id": "med_002",
        "sender": "press@techcrunch.com",
        "sender_domain": "techcrunch.com",
        "subject": "TechCrunch - Comment request on recent funding rumors",
        "body": (
            "Hi,\n\nI'm a reporter at TechCrunch. We've received information that your company "
            "may be raising a Series B round of $50M.\n\n"
            "Could you confirm or deny? We're publishing tomorrow at 9am EST.\n\n"
            "Best,\nAlex Rivera\nTechCrunch"
        ),
        "timestamp": "2024-01-15T14:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "press",
            "priority": "urgent",
            "department": "executive",
        },
        "expected_response_keywords": ["confirm", "deny", "statement", "PR"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
    {
        "id": "med_003",
        "sender": "dev@startup.io",
        "sender_domain": "startup.io",
        "subject": "API rate limit exceeded - breaking our production app",
        "body": (
            "Hello Support,\n\n"
            "We're hitting your API rate limit consistently and it's causing our production "
            "app to fail for end users. We're on the Pro plan.\n\n"
            "Error: 429 Too Many Requests\n"
            "Endpoint: /api/v2/process\n"
            "Rate: ~500 req/min (limit is 300)\n\n"
            "We need either a temporary limit increase or advice on optimization. "
            "This is actively hurting our customers.\n\nThanks,\nDev Team"
        ),
        "timestamp": "2024-01-15T15:00:00Z",
        "has_attachments": False,
        "thread_length": 3,
        "ground_truth": {
            "category": "technical_support",
            "priority": "urgent",
            "department": "engineering",
        },
        "expected_response_keywords": ["rate limit", "increase", "optimization", "workaround"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
    {
        "id": "med_004",
        "sender": "partner@bigco.com",
        "sender_domain": "bigco.com",
        "subject": "Partnership opportunity - integration with BigCo platform (500k users)",
        "body": (
            "Hi,\n\nI'm the Head of Partnerships at BigCo. We have 500,000 active users "
            "and are looking for integration partners for our platform.\n\n"
            "We believe there's a strong synergy between our platforms. "
            "Would you be open to an intro call this week?\n\nBest,\nJamie"
        ),
        "timestamp": "2024-01-15T16:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "partnership",
            "priority": "medium",
            "department": "sales",
        },
        "expected_response_keywords": ["schedule", "call", "partnership", "integration"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
    {
        "id": "med_005",
        "sender": "cfo@enterprise-client.com",
        "sender_domain": "enterprise-client.com",
        "subject": "Invoice dispute - overcharged by $12,400 on annual contract",
        "body": (
            "Dear Billing Team,\n\n"
            "We've reviewed invoice INV-2024-0088 for our annual renewal and believe "
            "we've been overcharged by $12,400.\n\n"
            "Our contract (attached) specifies 50 seats at $180/seat = $9,000. "
            "However you've invoiced us for $21,400 which doesn't match.\n\n"
            "Please review and issue a corrected invoice within 48 hours. "
            "Our accounts payable has put this on hold.\n\nBest,\nCFO"
        ),
        "timestamp": "2024-01-15T17:00:00Z",
        "has_attachments": True,
        "thread_length": 2,
        "ground_truth": {
            "category": "billing",
            "priority": "high",
            "department": "finance",
        },
        "expected_response_keywords": ["review", "correct", "invoice", "apologize", "48 hours"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
    {
        "id": "med_006",
        "sender": "newsletter@techdigest.com",
        "sender_domain": "techdigest.com",
        "subject": "Your weekly tech digest is here!",
        "body": (
            "This week in tech:\n- AI breakthroughs\n- New frameworks\n- Industry news\n\n"
            "Click here to read more...\n\nUnsubscribe | Manage preferences"
        ),
        "timestamp": "2024-01-15T09:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "spam",
            "priority": "ignore",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["medium"],
    },
    {
        "id": "med_007",
        "sender": "hr@yourcompany.com",
        "sender_domain": "yourcompany.com",
        "subject": "Action Required: Complete your annual compliance training by Friday",
        "body": (
            "Hi,\n\nThis is a reminder that all employees must complete the annual "
            "compliance training by this Friday, January 19th.\n\n"
            "Link: https://training.yourcompany.com/compliance-2024\n"
            "Estimated time: 45 minutes\n\n"
            "Non-completion may affect your performance review.\n\nHR Team"
        ),
        "timestamp": "2024-01-15T10:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "internal",
            "priority": "medium",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["medium"],
    },
    {
        "id": "med_008",
        "sender": "customer@smallbiz.net",
        "sender_domain": "smallbiz.net",
        "subject": "Question about upgrading our plan",
        "body": (
            "Hi,\n\nWe're currently on the Starter plan and wondering if the Pro plan "
            "would let us add more team members. We have 8 people now.\n\n"
            "Also what's the pricing difference?\n\nThanks,\nBob"
        ),
        "timestamp": "2024-01-15T13:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "sales_inquiry",
            "priority": "medium",
            "department": "sales",
        },
        "expected_response_keywords": ["pro plan", "pricing", "team", "upgrade"],
        "response_required": True,
        "tasks": ["medium", "hard"],
    },
]

# ─── HARD TASK (Task 3) ───────────────────────────────────────────────────────
# 10 emails including ambiguous cases, multi-intent, tricky priorities

HARD_EMAILS: List[EmailRecord] = [
    {
        "id": "hard_001",
        "sender": "ceo@acquirer.com",
        "sender_domain": "acquirer.com",
        "subject": "Confidential: Acquisition interest",
        "body": (
            "Hi,\n\nI'm the CEO of Acquirer Corp. We've been following your growth and "
            "believe there may be strategic value in a closer relationship.\n\n"
            "This is confidential, but we'd like to explore whether you'd be open to "
            "acquisition discussions. Our last deal was at 8x ARR.\n\n"
            "Would you or your board be available for a discreet conversation?\n\nBest,\nCEO"
        ),
        "timestamp": "2024-01-15T07:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "partnership",   # Could be executive/strategic
            "priority": "urgent",
            "department": "executive",
        },
        "expected_response_keywords": ["board", "consider", "schedule", "confidential"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_002",
        "sender": "security@unknown-domain.xyz",
        "sender_domain": "unknown-domain.xyz",
        "subject": "Security audit report - critical vulnerabilities found in your system",
        "body": (
            "Dear IT Team,\n\n"
            "I am an independent security researcher. I've discovered 3 critical "
            "vulnerabilities in your public API:\n\n"
            "1. SQL injection on /api/search endpoint\n"
            "2. Exposed admin panel at /admin (no auth)\n"
            "3. User data leak via IDOR on /api/users/{id}\n\n"
            "I'd like to work with you on responsible disclosure. "
            "I am not asking for payment but would appreciate acknowledgment.\n\n"
            "POC videos available on request.\n\nResearcher X"
        ),
        "timestamp": "2024-01-15T06:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "technical_support",  # Security incident
            "priority": "urgent",
            "department": "engineering",
        },
        "expected_response_keywords": ["security", "investigate", "responsible", "contact", "patch"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_003",
        "sender": "employee@yourcompany.com",
        "sender_domain": "yourcompany.com",
        "subject": "I need to talk about something serious",
        "body": (
            "Hi,\n\nI've been hesitating to send this but I feel I need to.\n\n"
            "I've witnessed what I believe is financial misconduct by my manager "
            "over the past few months. Specifically, I've seen expense reports being "
            "falsified and vendor payments going to a company I believe my manager owns.\n\n"
            "I'm not sure who to contact internally without it getting back to my manager. "
            "Can you point me to the right person or process?\n\n"
            "Please keep this confidential.\n\nA concerned employee"
        ),
        "timestamp": "2024-01-15T19:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "legal",
            "priority": "urgent",
            "department": "legal",
        },
        "expected_response_keywords": ["confidential", "HR", "legal", "whistleblower", "safe"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_004",
        "sender": "customer@enterprise.com",
        "sender_domain": "enterprise.com",
        "subject": "Re: Re: Re: Data export issue - going on 3 weeks now",
        "body": (
            "This is the 7th email on this thread. I've spoken to 4 different support reps "
            "and nobody has resolved it.\n\n"
            "My contract renews in 2 weeks. I will NOT renew unless this is fixed.\n\n"
            "I'm also considering refund for the 3 weeks of unusable service.\n\n"
            "> [Previous: 'We've escalated this to our engineering team']\n"
            "> [Previous: 'This is a known issue being worked on']\n"
            "> [Previous: 'We apologize for the delay']"
        ),
        "timestamp": "2024-01-15T20:00:00Z",
        "has_attachments": False,
        "thread_length": 7,
        "ground_truth": {
            "category": "customer_complaint",
            "priority": "urgent",
            "department": "support",
        },
        "expected_response_keywords": ["escalate", "engineer", "resolve", "personally", "compensate"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_005",
        "sender": "regulator@sec.gov",
        "sender_domain": "sec.gov",
        "subject": "SEC Inquiry - Request for Documents",
        "body": (
            "This is a formal request from the Securities and Exchange Commission.\n\n"
            "In connection with a non-public inquiry, we request the following documents "
            "be produced within 10 business days:\n\n"
            "1. All financial records from Q3-Q4 2023\n"
            "2. Board meeting minutes from Oct-Dec 2023\n"
            "3. Communications regarding [REDACTED]\n\n"
            "Failure to comply may result in a subpoena.\n\n"
            "Contact: investigator@sec.gov"
        ),
        "timestamp": "2024-01-15T12:00:00Z",
        "has_attachments": True,
        "thread_length": 1,
        "ground_truth": {
            "category": "legal",
            "priority": "urgent",
            "department": "legal",
        },
        "expected_response_keywords": ["legal", "counsel", "comply", "review", "immediately"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_006",
        "sender": "journalist@investigative-news.com",
        "sender_domain": "investigative-news.com",
        "subject": "Story about data breach - publishing tonight",
        "body": (
            "Hi,\n\nI'm an investigative journalist. I've obtained documents suggesting "
            "that your company experienced a data breach affecting 50,000 users in November "
            "that was not disclosed publicly.\n\n"
            "I'm publishing this story tonight at 6pm EST. "
            "Would you like to provide a comment?\n\nBest,\nJ. Thompson"
        ),
        "timestamp": "2024-01-15T09:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "press",
            "priority": "urgent",
            "department": "executive",
        },
        "expected_response_keywords": ["legal", "PR", "statement", "review", "respond"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_007",
        "sender": "vip@whale-customer.com",
        "sender_domain": "whale-customer.com",
        "subject": "Considering switching to competitor - need call with CTO today",
        "body": (
            "Hi,\n\nWe pay $180,000/year for your service. "
            "We've had 3 major outages this quarter that cost us significant revenue.\n\n"
            "I've been in discussions with your competitor. "
            "Before I finalize anything, I want to speak directly with your CTO today "
            "to understand your roadmap and get SLA commitments.\n\n"
            "If I can't get on a call today, I'll be signing with the competitor tomorrow.\n\n"
            "- CEO, Whale Customer"
        ),
        "timestamp": "2024-01-15T08:30:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "customer_complaint",
            "priority": "urgent",
            "department": "executive",  # High-value, needs exec attention
        },
        "expected_response_keywords": ["CTO", "schedule", "today", "SLA", "prioritize"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_008",
        "sender": "no-reply@phishing-bank-alert.com",
        "sender_domain": "phishing-bank-alert.com",
        "subject": "URGENT: Your bank account has been compromised - verify now",
        "body": (
            "Dear Customer,\n\n"
            "We have detected suspicious activity on your account. "
            "Please click here immediately: http://verify-your-account-now.biz/login\n\n"
            "Failure to verify within 24 hours will result in account suspension.\n\n"
            "Bank Security Team"
        ),
        "timestamp": "2024-01-15T11:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "spam",
            "priority": "ignore",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["hard"],
    },
    {
        "id": "hard_009",
        "sender": "contractor@freelancer.com",
        "sender_domain": "freelancer.com",
        "subject": "Invoice overdue 90 days - threatening small claims court",
        "body": (
            "This is my final notice.\n\n"
            "Invoice #2023-089 for $3,400 has been outstanding for 90 days. "
            "I have made 6 attempts to collect payment.\n\n"
            "If I do not receive payment by Friday, I will file in small claims court "
            "and report this to my professional network.\n\n"
            "I worked in good faith and completed all deliverables as agreed.\n\n"
            "- Alex M., Contractor"
        ),
        "timestamp": "2024-01-15T16:00:00Z",
        "has_attachments": True,
        "thread_length": 6,
        "ground_truth": {
            "category": "billing",
            "priority": "urgent",
            "department": "finance",
        },
        "expected_response_keywords": ["payment", "apologize", "process", "resolve", "week"],
        "response_required": True,
        "tasks": ["hard"],
    },
    {
        "id": "hard_010",
        "sender": "talent@bigtech.com",
        "sender_domain": "bigtech.com",
        "subject": "Recruiting your engineering team - we're hiring aggressively",
        "body": (
            "Hi,\n\nI'm a talent partner at BigTech. We're actively recruiting and "
            "your team has come up in our research.\n\n"
            "We're offering 2x market salary + significant equity for senior engineers. "
            "Would you be willing to share this opportunity with your team?\n\n"
            "We can also discuss your own role if you're open to it.\n\n"
            "Best,\nRecruiter"
        ),
        "timestamp": "2024-01-15T14:00:00Z",
        "has_attachments": False,
        "thread_length": 1,
        "ground_truth": {
            "category": "other",
            "priority": "low",
            "department": "ignore",
        },
        "expected_response_keywords": [],
        "response_required": False,
        "tasks": ["hard"],
    },
]

# ─── Task Definitions ─────────────────────────────────────────────────────────

TASKS = {
    "task_1_easy": {
        "id": "task_1_easy",
        "name": "Basic Email Triage",
        "difficulty": "easy",
        "description": (
            "Classify 5 straightforward emails with clear categories and priorities. "
            "Focus on: spam detection, sales inquiry identification, complaint urgency, "
            "and billing routing. Emails have unambiguous signals."
        ),
        "instructions": (
            "You are an email triage agent for a SaaS company. "
            "For each email, classify it with the correct:\n"
            "1. CATEGORY (spam, sales_inquiry, customer_complaint, billing, internal, etc.)\n"
            "2. PRIORITY (urgent, high, medium, low, ignore)\n"
            "3. DEPARTMENT to route to (support, sales, engineering, finance, legal, marketing, executive, ignore)\n\n"
            "Use action_type='classify' for each email."
        ),
        "emails": EASY_EMAILS,
        "scoring": {
            "category_weight": 0.40,
            "priority_weight": 0.35,
            "department_weight": 0.25,
        },
        "passing_score": 0.70,
    },
    "task_2_medium": {
        "id": "task_2_medium",
        "name": "Mixed Inbox Triage with Response Drafting",
        "difficulty": "medium",
        "description": (
            "Triage 8 emails including legal notices, press inquiries, partnership requests, "
            "billing disputes, and technical issues. Some emails require drafting a response. "
            "Priority assignment is more nuanced."
        ),
        "instructions": (
            "You are an email triage agent for a SaaS company. "
            "For each email:\n"
            "1. First CLASSIFY (category, priority, department)\n"
            "2. For emails marked as requiring a response, also RESPOND with a draft\n\n"
            "Pay special attention to:\n"
            "- Legal and press emails should be routed to executive/legal urgently\n"
            "- Billing disputes need finance routing\n"
            "- API/technical issues go to engineering\n"
            "- Spam and newsletters can be ignored\n\n"
            "Use action_type='classify' first, then action_type='respond' for response emails."
        ),
        "emails": EASY_EMAILS[:2] + EASY_EMAILS[3:5] + MEDIUM_EMAILS[:4],
        "scoring": {
            "category_weight": 0.30,
            "priority_weight": 0.30,
            "department_weight": 0.20,
            "response_quality_weight": 0.20,
        },
        "passing_score": 0.65,
    },
    "task_3_hard": {
        "id": "task_3_hard",
        "name": "Crisis Inbox: High-Stakes Triage",
        "difficulty": "hard",
        "description": (
            "Handle 10 high-stakes emails including acquisition inquiries, security disclosures, "
            "whistleblower reports, regulatory inquiries, and VIP customer churn risk. "
            "Errors in routing or priority can have severe consequences. "
            "Both classification accuracy AND response quality are graded."
        ),
        "instructions": (
            "You are the Chief of Staff at a fast-growing SaaS company. "
            "It's Monday morning and this is a critical inbox.\n\n"
            "For EVERY email:\n"
            "1. CLASSIFY with category, priority, and department\n"
            "2. Draft a RESPONSE for emails that require one\n"
            "3. ESCALATE emails that need immediate human executive attention\n\n"
            "Critical rules:\n"
            "- SEC/legal/regulatory = urgent + legal department, always escalate\n"
            "- Security vulnerabilities = urgent + engineering, always escalate\n"
            "- Whistleblower = urgent + legal, treat with extreme confidentiality\n"
            "- Press with negative story = urgent + executive\n"
            "- VIP customer churn = urgent + executive\n"
            "- Acquisition inquiry = urgent + executive\n"
            "- Phishing attempts = spam + ignore\n\n"
            "Your reputation depends on getting this right."
        ),
        "emails": HARD_EMAILS,
        "scoring": {
            "category_weight": 0.25,
            "priority_weight": 0.30,
            "department_weight": 0.25,
            "response_quality_weight": 0.20,
        },
        "passing_score": 0.60,
    },
}


def get_task(task_id: str) -> Dict[str, Any]:
    if task_id not in TASKS:
        raise ValueError(f"Unknown task: {task_id}. Valid tasks: {list(TASKS.keys())}")
    return TASKS[task_id]


def get_all_tasks() -> List[Dict[str, Any]]:
    return list(TASKS.values())
