# Autonomous Supply Chain Reroute Agent

Local MVP for simulating supply-chain disruptions, calculating capacity-aware alternative routes, and generating grounded OpenAI explanations.

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn backend.app.main:app --reload
cd frontend
npm install
npm run dev
pytest backend/tests
```

Set `OPENAI_API_KEY` in `.env` for provider-backed explanations. Without a key,
the API uses a clearly labeled deterministic/offline explanation fallback. The API
runs at `http://localhost:8000` and the React frontend at `http://localhost:5173`
during development.

## Demo

Open the React frontend, select **Singapore Port Closure**, plan from Shenzhen
Factory to Customer A, then run the affected-shipment batch. The command center
shows candidate routes, selected routes, affected shipments, capacity pressure,
grounded explanations, rerouting summaries, scenario history, and aggregate
metrics. The assistant also supports grounded questions about the currently
displayed route, disruption, shipment, cost, time, priority, and customer data.

## Project workflow

Project guidance and maintained technical documentation are indexed in
[`docs/README.md`](docs/README.md). Development uses local issues in
[`docs/issues/`](docs/issues/) and requires local verification plus the documented
demo gate before any GitHub push.

The source-neutral data preparation boundary is documented in
[`data/README.md`](data/README.md). Raw provider extracts belong under `data/raw/`
and must be normalized and validated before future database or graph loading.

The implemented runtime boundaries and source-of-truth model are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Remaining stabilization work is
prioritized in [`docs/REFACTOR_PLAN.md`](docs/REFACTOR_PLAN.md).
