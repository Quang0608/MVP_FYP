# Autonomous Supply Chain Reroute Agent

Local MVP for simulating supply-chain disruptions, calculating capacity-aware alternative routes, and generating grounded OpenAI explanations.

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn backend.app.main:app --reload
streamlit run dashboard/streamlit_app.py
pytest backend/tests
```

Set `OPENAI_API_KEY` in `.env` before calling `POST /reroute`; the project intentionally requires an API key for the single featured explanation. The API runs at `http://localhost:8000` and the dashboard at `http://localhost:8501`.

## Demo

Select **Singapore Closure**, simulate the disruption, then run the reroute agent. The dashboard shows affected shipments, candidate routes, selected routes, grounded explanations, and aggregate metrics.
