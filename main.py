from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.db import init_db, query_df
from app.llm import plan_query
from app.query_engine import execute, dataset_dates
from app.anomaly import detect_anomalies

BASE = Path(__file__).resolve().parent
init_db()

app = FastAPI(title="Support Ticket AI Analyst", version="1.0.0")

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

@app.get("/health")
def health():
    min_d, max_d = dataset_dates()
    return {"status":"ok", "tickets": int(query_df("SELECT COUNT(*) c FROM tickets").iloc[0].c),
            "dataset_start": str(min_d), "dataset_end": str(max_d)}

@app.post("/query")
def query(req: QueryRequest):
    try:
        min_d, max_d = dataset_dates()
        plan = plan_query(req.question, str(min_d.date()), str(max_d.date()))
        result = execute(plan)
        return {"question": req.question, "plan": plan, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/anomalies")
def anomalies():
    try:
        return detect_anomalies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def ui():
    return FileResponse(BASE / "static" / "index.html")
