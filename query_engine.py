from datetime import timedelta
import pandas as pd
from .db import query_df

ALLOWED = {
    "category": {"Billing", "Technical", "General"},
    "priority": {"Low", "Medium", "High", "Critical"},
    "status": {"Open", "Resolved", "Escalated"},
}

def dataset_dates():
    x = query_df("SELECT MIN(created_at) min_date, MAX(created_at) max_date FROM tickets").iloc[0]
    return pd.Timestamp(x.min_date), pd.Timestamp(x.max_date)

def _where(plan):
    f = plan.get("filters") or {}
    clauses, params = [], []
    for key in ("category", "priority", "agent_id"):
        val = f.get(key)
        if val is not None:
            if key in ALLOWED and val not in ALLOWED[key]:
                raise ValueError(f"Invalid {key}: {val}")
            if key == "agent_id" and (not isinstance(val, str) or len(val) > 20):
                raise ValueError("Invalid agent_id")
            clauses.append(f"{key} = ?")
            params.append(val)
    status = f.get("status")
    if status == "unresolved":
        clauses.append("status IN ('Open','Escalated')")
    elif status:
        if status not in ALLOWED["status"]:
            raise ValueError(f"Invalid status: {status}")
        clauses.append("status = ?")
        params.append(status)
    if f.get("created_after"):
        clauses.append("created_at >= ?"); params.append(f["created_after"] + " 00:00:00")
    if f.get("created_before"):
        clauses.append("created_at <= ?"); params.append(f["created_before"] + " 23:59:59")
    if f.get("resolution_gt_hours") is not None:
        n = float(f["resolution_gt_hours"])
        if n < 0 or n > 100000: raise ValueError("Invalid resolution threshold")
        clauses.append("resolution_time_hrs > ?"); params.append(n)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", tuple(params)

def execute(plan):
    intent = plan.get("intent", "list")
    metric = plan.get("metric")
    group = plan.get("group_by")
    limit = min(max(int(plan.get("limit") or 20), 1), 100)
    where, params = _where(plan)

    if intent == "anomaly":
        from .anomaly import detect_anomalies
        return detect_anomalies()

    if group:
        if group not in {"agent_id","category","priority","status","date"}:
            raise ValueError("Unsupported group_by")
        gexpr = "date(created_at)" if group == "date" else group
        if metric == "avg_customer_rating":
            select = f"{gexpr} AS group_value, ROUND(AVG(customer_rating), 2) AS value"
            order = "value ASC"
            null_filter = " AND customer_rating IS NOT NULL"
        elif metric == "avg_response_time":
            select = f"{gexpr} AS group_value, ROUND(AVG(response_time_hrs), 2) AS value"
            order = "value DESC"; null_filter = ""
        elif metric == "avg_resolution_time":
            select = f"{gexpr} AS group_value, ROUND(AVG(resolution_time_hrs), 2) AS value"
            order = "value DESC"; null_filter = " AND resolution_time_hrs IS NOT NULL"
        else:
            select = f"{gexpr} AS group_value, COUNT(*) AS value"
            order = "value DESC"; null_filter = ""
        sql = f"SELECT {select} FROM tickets{where}{null_filter} GROUP BY {gexpr} ORDER BY {order} LIMIT {limit}"
        rows = query_df(sql, params)
        return {"type":"grouped", "data": rows.to_dict(orient="records"), "sql": sql}

    if metric == "avg_customer_rating":
        sql = f"SELECT ROUND(AVG(customer_rating), 2) AS value FROM tickets{where} AND customer_rating IS NOT NULL" if where else "SELECT ROUND(AVG(customer_rating), 2) AS value FROM tickets WHERE customer_rating IS NOT NULL"
    elif metric == "avg_response_time":
        sql = f"SELECT ROUND(AVG(response_time_hrs), 2) AS value FROM tickets{where}"
    elif metric == "avg_resolution_time":
        sql = f"SELECT ROUND(AVG(resolution_time_hrs), 2) AS value FROM tickets{where} AND resolution_time_hrs IS NOT NULL" if where else "SELECT ROUND(AVG(resolution_time_hrs), 2) AS value FROM tickets WHERE resolution_time_hrs IS NOT NULL"
    else:
        sql = f"SELECT COUNT(*) AS value FROM tickets{where}"
    rows = query_df(sql, params)
    return {"type":"scalar", "data": rows.to_dict(orient="records"), "sql": sql}

def natural_query(plan):
    # Resolve relative time expressions deterministically using the dataset's latest date.
    f = plan.setdefault("filters", {})
    min_d, max_d = dataset_dates()
    # The LLM may express relative windows in optional metadata.
    relative = plan.pop("relative_time", None)
    if relative == "this_week":
        f["created_after"] = (max_d - timedelta(days=7)).strftime("%Y-%m-%d")
        f["created_before"] = max_d.strftime("%Y-%m-%d")
    elif relative == "this_month":
        f["created_after"] = max_d.replace(day=1).strftime("%Y-%m-%d")
        f["created_before"] = max_d.strftime("%Y-%m-%d")
    return execute(plan)
