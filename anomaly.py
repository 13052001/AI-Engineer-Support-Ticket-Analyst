import pandas as pd
from .db import query_df
from .query_engine import dataset_dates

def detect_anomalies():
    df = query_df("SELECT * FROM tickets")
    max_date = pd.Timestamp(df["created_at"].max())
    df["created_at"] = pd.to_datetime(df["created_at"])
    resolved = df["resolution_time_hrs"].dropna()
    q1, q3 = resolved.quantile([0.25, 0.75])
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr

    long_resolution = df[df["resolution_time_hrs"] > upper].copy()
    old_unresolved = df[
        df["status"].isin(["Open","Escalated"]) &
        df["priority"].isin(["High","Critical"]) &
        ((max_date - df["created_at"]).dt.total_seconds() > 24*3600)
    ].copy()
    week_start = max_date - pd.Timedelta(days=7)
    week = df[(df["created_at"] >= week_start) & (df["created_at"] <= max_date)]
    week_long = week[week["resolution_time_hrs"] > upper].copy()

    def records(x):
        cols = ["ticket_id","created_at","category","priority","status","resolution_time_hrs","agent_id","issue_summary"]
        x = x[cols].copy()
        x["created_at"] = x["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        return x.to_dict(orient="records")

    return {
        "method": "IQR upper-bound + SLA-style age rule",
        "dataset_window": {"start": str(df.created_at.min()), "end": str(max_date)},
        "resolution_iqr": {
            "q1": round(float(q1),2), "q3": round(float(q3),2),
            "iqr": round(float(iqr),2), "upper_bound_hours": round(float(upper),2)
        },
        "summary": {
            "long_resolution_anomalies": len(long_resolution),
            "unresolved_high_priority_older_than_24h": len(old_unresolved),
            "long_resolution_anomalies_this_week": len(week_long)
        },
        "long_resolution_tickets": records(long_resolution.sort_values("resolution_time_hrs", ascending=False)),
        "old_unresolved_high_priority": records(old_unresolved.sort_values("created_at"))
    }
