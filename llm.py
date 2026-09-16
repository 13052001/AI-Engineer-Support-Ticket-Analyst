import json
import re
import httpx
from .config import settings

SCHEMA = {
    "intent": "count|aggregate|list|anomaly",
    "filters": {
        "category": "Billing|Technical|General|null",
        "priority": "Low|Medium|High|Critical|null",
        "status": "Open|Resolved|Escalated|unresolved|null",
        "agent_id": "AGT-XX|null",
        "created_after": "YYYY-MM-DD|null",
        "created_before": "YYYY-MM-DD|null",
        "resolution_gt_hours": "number|null"
    },
    "metric": "count|avg_customer_rating|avg_response_time|avg_resolution_time|null",
    "group_by": "agent_id|category|priority|status|date|null",
    "limit": "integer|null",
    "relative_time": "this_week|this_month|null"
}

SYSTEM_PROMPT = """You convert customer-support questions into a safe structured query plan.
Return ONLY valid JSON. Never write SQL and never invent columns.

Dataset columns:
ticket_id, created_at, category, priority, status, response_time_hrs,
resolution_time_hrs, agent_id, customer_rating, issue_summary.

Semantics:
- "unresolved" means status is Open OR Escalated.
- Dates refer to created_at.
- "this week" means the last 7 days ending at the dataset's latest created_at.
- "this month" means the calendar month containing the dataset's latest created_at unless an explicit date is supplied.
- If a question asks "which agent", use group_by=agent_id.
- "lowest average customer rating" => metric=avg_customer_rating, group_by=agent_id.
- "most resolved" => count resolved tickets, group_by=agent_id, with status=Resolved.
- "critical tickets not resolved within N hours" => priority=Critical, status=unresolved, resolution_gt_hours=N.
- Use null when a field is not needed.
Schema:
""" + json.dumps(SCHEMA, indent=2)

def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM did not return JSON")
    return json.loads(text[start:end+1])

def plan_query(question: str, dataset_min_date: str, dataset_max_date: str) -> dict:
    prompt = f"""Dataset date range: {dataset_min_date} through {dataset_max_date}.
Question: {question}
Return the JSON query plan only."""
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        payload = {
            "model": settings.groq_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role":"system","content":SYSTEM_PROMPT},
                         {"role":"user","content":prompt}]
        }
        with httpx.Client(timeout=45) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return _extract_json(r.json()["choices"][0]["message"]["content"])

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role":"system","content":SYSTEM_PROMPT},
                     {"role":"user","content":prompt}]
    }
    with httpx.Client(timeout=90) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return _extract_json(r.json()["message"]["content"])
