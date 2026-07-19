# Autonomous Supply Chain Reroute Agent — Project Brief for Codex

## 1. Project Title

**Autonomous Supply Chain Reroute Agent Using Graph Analytics, Neo4j, FastAPI, Streamlit, and OpenAI API**

## 2. Project Objective

This project develops an autonomous supply chain rerouting system that can simulate logistics disruptions, identify affected shipments, calculate alternative delivery paths, and generate human-readable recommendations using an LLM agent.

The final deliverable is a functional dashboard that demonstrates a port closure scenario and shows how the system autonomously detects affected shipments, evaluates alternative routes, and recommends the best rerouting plan.

The system should be designed as a hybrid architecture:

- **Graph engine** handles truth, routing, dependencies, and calculations.
- **Optimization/scoring logic** ranks alternative routes based on time, cost, risk, and capacity.
- **LLM agent using OpenAI API** explains the recommendation and creates an operational action plan.
- **Dashboard** allows users to simulate disruption scenarios and view rerouting results.

The LLM must not invent routes, costs, shipment IDs, or ports. It should only explain results produced by deterministic backend logic.

---

## 3. Core Problem Statement

Global supply chains can be disrupted by port closures, route blockages, factory shutdowns, weather events, congestion, and geopolitical issues. When a disruption happens, logistics teams need to know:

1. Which shipments are affected?
2. Which customers, warehouses, or downstream nodes will be impacted?
3. What alternative routes are available?
4. Which alternative route is best based on delay, cost, risk, and capacity?
5. What action should the logistics team take?

This project builds a prototype system that answers these questions using a graph-based supply chain model and an LLM-based explanation layer.

---

## 4. Expected Final Demo

The dashboard should support this demo flow:

1. User opens the dashboard and sees a supply chain network map.
2. User selects a disruption scenario, for example:
   - `Port of Singapore closed for 72 hours`
3. System marks the disrupted port and related routes as unavailable.
4. System identifies affected shipments whose planned routes pass through the disrupted node.
5. System calculates alternative routes that avoid the disrupted node.
6. System scores each alternative route by time, cost, risk, and capacity.
7. System selects the best route.
8. OpenAI-powered agent explains:
   - why the shipment is affected
   - what route is recommended
   - delay saved
   - additional cost
   - operational next steps
9. Dashboard displays:
   - disrupted node
   - affected shipments
   - original blocked route
   - recommended alternative route
   - route comparison table
   - LLM-generated recommendation
   - evaluation metrics

---

## 5. Strong Final Tech Stack

Use the stronger final version stack:

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy where useful
- pytest

### Dashboard

- Streamlit for MVP dashboard
- Plotly for charts
- Folium / PyVis / NetworkX drawing for graph or map visualization

### Graph Layer

- Neo4j graph database
- Neo4j Python driver
- Cypher queries
- NetworkX for algorithm prototyping and fallback graph algorithms
- Optional later: Neo4j Graph Data Science

### Relational / App Data Storage

- PostgreSQL for structured application data, or SQLite for early local MVP
- Tables for shipments, disruptions, reroute recommendations, experiment results

### LLM / Agent Layer

- OpenAI API
- Structured JSON output where possible
- Tool-calling style design
- Agent should call backend functions, not guess answers
- Optional later: LangChain or LlamaIndex, but start simple with custom Python service

### RAG / Policy Layer, Advanced Phase

- Simple markdown policy documents first
- Later optional vector database for logistics policies and company rules

### Deployment / Engineering

- Docker
- `.env` for API keys and database connection strings
- Makefile or task scripts
- Clear README
- Tests for route calculation, impact analysis, scoring, and agent output formatting

---

## 6. Main Components to Build

### 6.1 Data Models

Create models/entities for:

#### Location

Represents supply chain nodes.

Fields:

- `id`
- `name`
- `type`: `FACTORY`, `PORT`, `WAREHOUSE`, `CUSTOMER`
- `country`
- `latitude`
- `longitude`
- `status`: `ACTIVE`, `DISRUPTED`
- `capacity`

#### Route

Represents edges between locations.

Fields:

- `id`
- `source_location_id`
- `destination_location_id`
- `mode`: `SEA`, `ROAD`, `RAIL`, `AIR`
- `normal_duration_hours`
- `current_duration_hours`
- `cost`
- `risk_score`
- `capacity`
- `current_load`
- `status`: `ACTIVE`, `BLOCKED`

#### Shipment

Represents shipment movement from origin to destination.

Fields:

- `id`
- `origin_id`
- `destination_id`
- `current_location_id`
- `planned_route_location_ids`
- `deadline`
- `priority`: `LOW`, `MEDIUM`, `HIGH`
- `status`: `ON_TIME`, `AT_RISK`, `DELAYED`, `REROUTED`

#### Disruption

Represents disruption events.

Fields:

- `id`
- `affected_location_id`
- `affected_route_id`, optional
- `type`: `PORT_CLOSURE`, `FACTORY_SHUTDOWN`, `ROUTE_BLOCKED`, `CONGESTION`
- `start_time`
- `estimated_end_time`
- `severity`: `LOW`, `MEDIUM`, `HIGH`
- `description`

#### RerouteRecommendation

Stores generated recommendations.

Fields:

- `id`
- `shipment_id`
- `disruption_id`
- `original_route`
- `recommended_route`
- `delay_saved_hours`
- `additional_cost`
- `risk_score`
- `route_score`
- `llm_explanation`
- `created_at`

---

## 7. Required Backend Services

Implement the backend in a modular way.

Recommended service modules:

```text
backend/
  app/
    main.py
    config.py
    api/
      routes.py
      disruptions.py
      shipments.py
      recommendations.py
    models/
      location.py
      route.py
      shipment.py
      disruption.py
      recommendation.py
    schemas/
      location_schema.py
      route_schema.py
      shipment_schema.py
      disruption_schema.py
      recommendation_schema.py
    services/
      graph_service.py
      disruption_service.py
      impact_service.py
      route_planner_service.py
      route_scoring_service.py
      llm_agent_service.py
      simulation_service.py
    repositories/
      neo4j_repository.py
      shipment_repository.py
      disruption_repository.py
    tests/
      test_impact_service.py
      test_route_planner_service.py
      test_route_scoring_service.py
      test_llm_agent_service.py
```

---

## 8. Core Backend Functions

Implement these functions first:

```python
def build_supply_chain_graph(locations, routes):
    """Build an in-memory graph from locations and routes."""


def apply_disruption(graph, disruption):
    """Mark affected node or route as blocked/unavailable."""


def find_affected_shipments(shipments, disrupted_location_id):
    """Return shipments whose planned route contains the disrupted location."""


def find_downstream_impacts(graph, disrupted_location_id):
    """Find downstream warehouses/customers affected by the disruption."""


def find_candidate_routes(graph, origin_id, destination_id, avoid_nodes=None, k=3):
    """Find top-k alternative routes avoiding disrupted nodes."""


def score_route(route, shipment_priority):
    """Score route based on time, cost, risk, and capacity."""


def select_best_route(scored_routes):
    """Return the route with the lowest score."""


def generate_llm_recommendation(disruption, shipment, original_route, candidate_routes, selected_route):
    """Use OpenAI API to generate a grounded explanation."""
```

---

## 9. Route Scoring Logic

Use a transparent scoring formula.

Initial scoring formula:

```text
route_score =
    0.45 * normalized_time
  + 0.30 * normalized_cost
  + 0.15 * normalized_risk
  + 0.10 * capacity_penalty
```

Lower score means better route.

Adjust priority behavior:

- High-priority shipments should weight time more heavily.
- Low-priority shipments can weight cost more heavily.
- Routes passing through disrupted nodes should be invalid.
- Routes exceeding capacity should receive a penalty or be rejected.

Suggested priority-specific weights:

```text
HIGH priority:
  time = 0.60
  cost = 0.20
  risk = 0.15
  capacity = 0.05

MEDIUM priority:
  time = 0.45
  cost = 0.30
  risk = 0.15
  capacity = 0.10

LOW priority:
  time = 0.30
  cost = 0.45
  risk = 0.15
  capacity = 0.10
```

---

## 10. LLM Agent Requirements

Use OpenAI API for the LLM layer.

The LLM should only receive structured input produced by the backend.

The LLM should output:

- summary of disruption
- affected shipment explanation
- selected route explanation
- trade-off analysis
- operational action plan
- warning if no feasible route exists

The LLM must obey these rules:

1. Do not invent shipment IDs.
2. Do not invent locations.
3. Do not invent routes.
4. Do not invent costs, risk scores, or delay values.
5. Only use the candidate routes provided by the backend.
6. If no route exists, say no feasible route exists.
7. Explain in clear business language.
8. Return structured JSON where useful.

Suggested output shape:

```json
{
  "summary": "...",
  "recommended_action": "...",
  "reasoning_summary": "...",
  "delay_saved_hours": 0,
  "additional_cost": 0,
  "risk_warning": "...",
  "next_steps": ["...", "...", "..."]
}
```

---

## 11. FastAPI Endpoints

Implement these endpoints:

```text
GET /health
GET /locations
GET /routes
GET /shipments
GET /disruptions
POST /simulate-disruption
POST /reroute
GET /recommendations
GET /metrics
```

### `POST /simulate-disruption`

Input:

```json
{
  "disruption_type": "PORT_CLOSURE",
  "affected_location_id": "P_SG",
  "duration_hours": 72,
  "severity": "HIGH"
}
```

Output:

```json
{
  "disruption_id": "D001",
  "affected_shipments": [...],
  "downstream_impacts": [...]
}
```

### `POST /reroute`

Input:

```json
{
  "disruption_id": "D001"
}
```

Output:

```json
{
  "recommendations": [
    {
      "shipment_id": "S001",
      "original_route": [...],
      "candidate_routes": [...],
      "selected_route": [...],
      "route_score": 0.42,
      "delay_saved_hours": 58,
      "additional_cost": 1100,
      "llm_explanation": "..."
    }
  ]
}
```

---

## 12. Dashboard Requirements

Build the MVP dashboard in Streamlit first.

Dashboard sections:

1. Supply chain network view
2. Disruption simulator panel
3. Affected shipments table
4. Alternative route comparison table
5. Agent recommendation panel
6. Evaluation metrics panel

The dashboard should allow the user to:

- select a disruption type
- select affected port/factory/route
- set disruption duration
- run simulation
- run reroute agent
- view recommendations

Minimum dashboard workflow:

```text
Select: Port of Singapore
Select: Port closure
Input: 72 hours
Click: Simulate disruption
Click: Run reroute agent
View: affected shipments, alternative routes, best recommendation, LLM explanation
```

---

## 13. MVP Dataset

Create synthetic seed data.

Minimum data:

### Locations

- Shenzhen Factory
- Ho Chi Minh Factory
- Bangkok Factory
- Singapore Port
- Port Klang
- Tanjung Pelepas Port
- Laem Chabang Port
- Singapore Warehouse
- Malaysia Warehouse
- Australia Warehouse
- Customer A
- Customer B
- Customer C

### Routes

Create routes between factories, ports, warehouses, and customers.

Each route must have:

- mode
- duration
- cost
- risk score
- capacity

### Shipments

Create at least 30 sample shipments.

Each shipment should have:

- origin
- destination
- planned route
- deadline
- priority

### Disruption Scenarios

Create at least 5 scenarios:

1. Singapore Port closed for 72 hours
2. Port Klang congestion by 50%
3. Shenzhen Factory shutdown
4. Road route from Port Klang to Singapore Warehouse blocked
5. Multiple port disruption scenario

---

## 14. Evaluation Metrics

Implement basic metrics for the MVP:

- number of affected shipments
- number of successfully rerouted shipments
- rerouting success rate
- average delay saved
- total additional cost
- average route risk
- algorithm response time
- LLM explanation generated or failed

Example output:

```json
{
  "affected_shipments": 25,
  "successfully_rerouted": 22,
  "reroute_success_rate": 0.88,
  "average_delay_saved_hours": 46,
  "total_additional_cost": 15400,
  "average_route_risk": 0.31
}
```

---

## 15. Development Phases for Codex

Codex should not implement everything at once.

Follow this order strictly.

### Phase 0 — Review and Planning Only

Do not write production code yet.

Tasks:

1. Review this project brief.
2. Identify missing requirements or risky assumptions.
3. Propose final architecture.
4. Propose repository structure.
5. Propose implementation phases.
6. List core modules and responsibilities.
7. List data models and schemas.
8. List API endpoints.
9. List test strategy.
10. Ask clarification questions only if truly blocking.

Expected output:

- architecture plan
- file structure
- implementation roadmap
- testing plan
- MVP scope
- advanced feature backlog

### Phase 1 — Codebase Skeleton

Build the initial repo structure.

Tasks:

1. Create backend FastAPI app skeleton.
2. Create Streamlit dashboard skeleton.
3. Add config management.
4. Add environment variable loading.
5. Add seed data files.
6. Add README.
7. Add Makefile or task commands.
8. Add requirements or pyproject file.
9. Add pytest setup.
10. Add Dockerfile and docker-compose if feasible.

Do not implement advanced algorithms yet.

### Phase 2 — Data and Graph Foundation

Tasks:

1. Implement synthetic data loading.
2. Implement location, route, shipment, disruption models.
3. Implement NetworkX graph builder.
4. Implement basic Neo4j repository and seed loading.
5. Implement graph query functions.
6. Add tests for graph creation and data loading.

### Phase 3 — Disruption and Impact Analysis

Tasks:

1. Implement disruption application logic.
2. Implement affected shipment detection.
3. Implement downstream impact detection.
4. Add FastAPI endpoints for simulation.
5. Add tests for disruption scenarios.

### Phase 4 — Rerouting MVP

Tasks:

1. Implement candidate route search.
2. Implement route scoring.
3. Implement best route selection.
4. Implement reroute endpoint.
5. Add tests for route scoring and route selection.
6. Handle no-route-found cases.

### Phase 5 — OpenAI LLM Agent

Tasks:

1. Implement OpenAI client wrapper.
2. Implement grounded prompt template.
3. Implement structured recommendation output.
4. Add fallback behavior when API key is missing.
5. Add tests using mocked LLM responses.
6. Ensure the LLM cannot invent unsupported data.

### Phase 6 — MVP Dashboard

Tasks:

1. Build Streamlit dashboard.
2. Add disruption input controls.
3. Show network visualization.
4. Show affected shipment table.
5. Show route comparison table.
6. Show selected recommendation.
7. Show LLM explanation.
8. Show evaluation metrics.

### Phase 7 — Evaluation and Experiments

Tasks:

1. Create experiment runner.
2. Run predefined disruption scenarios.
3. Store metrics.
4. Display evaluation results in dashboard.
5. Add report-ready output tables.

### Phase 8 — Advanced Features Later

Do not implement these until the MVP works.

Backlog:

1. Neo4j Graph Data Science shortest path.
2. k-shortest path alternatives.
3. Capacity-aware multi-shipment assignment.
4. Linear programming optimization.
5. RAG over logistics policy documents.
6. Real-time shipment movement simulation.
7. Event-driven architecture.
8. Weather/news disruption ingestion.
9. Better map visualization using Leaflet.
10. Multi-agent design with separate impact, routing, and explanation agents.

---

## 16. Important Implementation Rules

Codex should follow these rules:

1. Build incrementally.
2. Do not over-engineer the first version.
3. Keep business logic separate from API routes.
4. Keep LLM code separate from graph/routing logic.
5. Ensure the system works even without OpenAI API key by using a mock explanation.
6. Write tests for deterministic logic.
7. Use clear type hints and docstrings.
8. Use small, readable functions.
9. Do not put API keys in code.
10. Use `.env.example` for required environment variables.
11. Prefer simple working MVP over unfinished complex design.
12. Use synthetic data first.
13. Do not rely on real logistics APIs in the MVP.
14. The LLM must be grounded in backend-generated data.
15. The dashboard must demonstrate the complete flow end to end.

---

## 17. Suggested Environment Variables

Create `.env.example`:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reroute_agent
APP_ENV=development
```

For local MVP, SQLite can be used first if PostgreSQL setup slows progress.

---

## 18. Suggested README Commands

The README should include commands like:

```bash
# install dependencies
pip install -r requirements.txt

# run backend
uvicorn backend.app.main:app --reload

# run dashboard
streamlit run dashboard/streamlit_app.py

# run tests
pytest

# run with docker
docker compose up --build
```

---

## 19. Expected MVP Acceptance Criteria

The MVP is complete when:

1. The backend starts successfully.
2. The dashboard starts successfully.
3. Synthetic supply chain data loads successfully.
4. User can simulate Singapore Port closure.
5. System identifies affected shipments.
6. System finds at least one alternative route for some shipments.
7. System scores candidate routes.
8. System selects best route.
9. LLM or mock LLM generates explanation.
10. Dashboard displays the full result clearly.
11. Tests pass for graph, disruption, route scoring, and rerouting logic.

---

## 20. Prompt to Use With Codex

Use this prompt when asking Codex to start:

```text
You are helping me build my FYP project: Autonomous Supply Chain Reroute Agent.

Before writing code, review PROJECT_BRIEF_FOR_CODEX.md carefully and produce a detailed implementation plan.

Do not implement code yet.

I want you to:
1. Check whether the architecture is reasonable.
2. Identify missing requirements or risks.
3. Propose the final repository structure.
4. Break the work into implementation phases.
5. Define the exact MVP scope.
6. Define what should be postponed to advanced features.
7. Propose testing strategy.
8. Propose how to keep the LLM grounded and prevent hallucination.

After I approve the plan, then implement Phase 1 only: codebase skeleton.
```

After Codex gives a plan and you approve it, use:

```text
Proceed with Phase 1 only.

Create the initial codebase skeleton for the project.
Do not implement advanced algorithms yet.
Focus on clean structure, config, dependency setup, seed data placeholders, FastAPI skeleton, Streamlit skeleton, tests setup, README, and .env.example.

After implementation, summarize:
1. files created
2. how to run backend
3. how to run dashboard
4. how to run tests
5. what Phase 2 should implement next
```

After Phase 1 is done, use:

```text
Proceed with Phase 2.

Implement the data and graph foundation:
1. synthetic data loading
2. location, route, shipment, and disruption schemas
3. NetworkX graph builder
4. basic Neo4j repository if feasible
5. tests for data loading and graph creation

Do not implement LLM or dashboard features yet unless required for smoke testing.
```

After Phase 2 is done, use:

```text
Proceed with Phase 3 and Phase 4.

Implement disruption impact analysis and rerouting MVP:
1. apply disruption to graph
2. find affected shipments
3. find downstream impacts
4. find candidate alternative routes
5. score routes
6. select best route
7. expose FastAPI endpoints for simulate-disruption and reroute
8. add unit tests for each deterministic function

Do not implement advanced optimization yet.
```

After Phase 3 and 4 are done, use:

```text
Proceed with Phase 5.

Implement the OpenAI-based LLM agent layer:
1. OpenAI client wrapper
2. grounded prompt template
3. structured JSON output
4. fallback mock explanation when OPENAI_API_KEY is missing
5. tests with mocked LLM response

Important: the LLM must only explain backend-generated route data. It must not invent routes, costs, locations, or shipment IDs.
```

After Phase 5 is done, use:

```text
Proceed with Phase 6.

Build the MVP Streamlit dashboard:
1. disruption simulator controls
2. supply chain graph or map visualization
3. affected shipments table
4. candidate route comparison table
5. selected recommendation section
6. LLM explanation section
7. evaluation metrics section

Make sure the dashboard demonstrates the full end-to-end flow using the synthetic Singapore Port closure scenario.
```

---

## 21. Final Reminder

The project should be presented as:

> A hybrid graph-based and LLM-based autonomous rerouting system for supply chain disruption response.

The strongest design principle is:

> Graph algorithms calculate the truth. The LLM explains the decision.
