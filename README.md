# Support Ticket AI Analyst — AI Engineer Assessment

An end-to-end Python AI system for the DOTMappers AI Engineer assessment. It ingests the provided 500-row support ticket CSV into SQLite, uses an LLM to convert natural-language questions into a validated structured query plan, executes that plan deterministically, and exposes both REST APIs and a minimal web UI.

## Requirements covered

1. CSV ingestion + queryable storage: SQLite.
2. Natural-language questions: LLM planner (Ollama by default; Groq free tier optional).
3. Anomaly detection:
   - resolution-time outliers using the IQR upper bound;
   - unresolved High/Critical tickets older than 24 hours;
   - weekly resolution outliers based on the dataset's latest timestamp.
4. REST API + minimal UI: FastAPI and a static HTML interface.

## Architecture

```text
support_tickets.csv
       |
       v
   SQLite DB  <---- deterministic query engine
       ^
       |
FastAPI ---> LLM planner ---> JSON query plan ---> validation ---> SQL
   |
   +---- /health
   +---- /query
   +---- /anomalies
   |
   +---- browser UI (/)
```

Important design choice: the LLM never writes or executes SQL. It only produces a small JSON plan. The application validates the plan and builds SQL from an allow-list. This reduces prompt-injection and SQL-generation risk while keeping the natural-language layer flexible.

## Setup

### Option A — Ollama (recommended, zero API cost)

Install Ollama, then pull a small local model:

```bash
ollama pull llama3.2:3b
```

Create an environment if desired:

```bash
cp .env.example .env
```

Install dependencies and start:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

On Windows, activate the venv using `.venv\Scripts\activate`.

### Option B — Groq free tier

Set:

```text
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
```

Then run the same `uvicorn main:app --reload` command. No paid API is required.

## API

### Health

`GET /health`

### Natural-language query

`POST /query`

Body:

```json
{"question":"Which agent has the lowest average customer rating?"}
```

Response contains the original question, the LLM-generated plan, and the deterministic query result.

### Anomalies

`GET /anomalies`

## Example results from the supplied dataset

The supplied dataset contains 500 tickets spanning 2024-01-01 through 2024-03-30.

- Currently open: **111**
- Critical + unresolved: **31**
- Average Technical customer rating: **3.74**
- Lowest average customer rating by agent: **AGT-08, 3.48**
- Resolution-time IQR upper bound: **48.15 hours**
- Resolution-time outliers: **21**
- Unresolved High/Critical tickets older than 24 hours: **80**
- Resolution-time outliers in the dataset's latest 7-day window: **6**

## Handling "this week" and "this month"

The data is historical (ending 2024-03-30), so relative periods are anchored to the dataset's latest `created_at` rather than the machine's current date. This makes the application reproducible during evaluation.

## Known limitations

- The LLM must be available through Ollama or Groq; the assessment explicitly requires an LLM.
- The planner intentionally supports a constrained query vocabulary instead of arbitrary SQL.
- "Anomaly" is a rule-based detection layer, not a trained ML anomaly model. IQR is transparent and reproducible for this small dataset.
- Customer ratings and resolution times are null for unresolved tickets and are excluded from their respective averages.
- The sample CSV is loaded once into `support_tickets.db`; deleting the DB and restarting re-ingests the CSV.

## Testing examples

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How many tickets are currently open?"}'

curl http://127.0.0.1:8000/anomalies
```

## Assessment trade-offs

SQLite was chosen because the supplied dataset is only 500 rows, requires no external service, and is easy for an evaluator to run locally. FastAPI provides typed validation and a clean REST surface. The LLM is isolated to intent/parameter extraction, while aggregation and anomaly calculations remain deterministic and testable.

For a production version, I would add authentication, request tracing, persistent model/provider health checks, a richer query grammar, automated tests, and a proper observability layer.
