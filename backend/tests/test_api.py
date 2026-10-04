import os
from datetime import date

import pandas as pd
os.environ["DATABASE_URL"]="sqlite://"

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.main import app
from backend.app.config import settings
from backend.app.repository import (
    AgentDecisionRecord,
    DisruptionLocationRecord,
    LocationRecord,
    RouteRecord,
    Session,
    ShipmentRecord,
    ShipmentRouteLegRecord,
    SimulationRunRecord,
    load_runtime_dataset,
)
from backend.app.domain import Location, Route, Shipment, ShipmentRouteLeg


def test_health_and_locations():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"]=="ok"
        assert len(client.get("/locations").json()) >= 13
        routes_response = client.get("/routes")
        corridors_response = client.get("/network/corridors")
        assert routes_response.status_code == 200
        sea_routes = [item for item in routes_response.json() if item["mode"] == "SEA"]
        assert sea_routes
        assert all(len(item["weather_sample_points"]) == 5 for item in sea_routes)
        assert all(item["corridor_ids"] for item in sea_routes)
        assert corridors_response.status_code == 200
        assert {item["id"] for item in corridors_response.json()} >= {
            "CHK_SUEZ",
            "CHK_MALACCA",
        }
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(LocationRecord)) == 91
        assert session.scalar(select(func.count()).select_from(RouteRecord)) == 150
        assert session.scalar(select(func.count()).select_from(ShipmentRecord)) == 220
        assert (
            session.scalar(select(func.count()).select_from(ShipmentRouteLegRecord))
            == 1000
        )
    dataset = load_runtime_dataset()
    assert all(isinstance(item, Location) for item in dataset.locations)
    assert all(isinstance(item, Route) for item in dataset.routes)
    assert all(isinstance(item, Shipment) for item in dataset.shipments)
    assert all(
        isinstance(leg, ShipmentRouteLeg)
        for shipment in dataset.shipments
        for leg in shipment.route_legs
    )
    assert all(
        len(route.weather_sample_points) == 5
        and route.corridor_ids
        for route in dataset.routes
        if route.transport_mode == "SEA"
    )
    first = next(shipment for shipment in dataset.shipments if shipment.id == "ASIA_S_0021")
    assert first.route_legs[0].status == "CURRENT"
    assert all(leg.status == "PLANNED" for leg in first.route_legs[1:])


def test_weather_debug_endpoint_is_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "open_meteo_enabled", False)
    with TestClient(app) as client:
        response = client.get("/weather/routes/ASIA_R_0056/raw")
    assert response.status_code == 503
    assert response.json()["detail"] == "Open-Meteo integration is disabled"


def test_external_signal_exposure_debug_endpoint_does_not_apply_network_effects():
    with TestClient(app) as client:
        response = client.post(
            "/external-signals/exposure",
            json={
                "id": "SIG-API-001",
                "source": "MANUAL",
                "source_record_id": "fixture-001",
                "signal_type": "PORT_CLOSURE",
                "target_type": "LOCATION",
                "target_id": "LOC_WPI_50000",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2026-12-31T00:00:00Z",
                "status": "ACTIVE",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["network_match"]["affected_locations"] == ["LOC_WPI_50000"]
    assert payload["exposed_shipments"]
    assert all(
        item["match_type"] == "LOCATION"
        for item in payload["exposed_shipments"]
    )


def test_portwatch_state_is_visible_on_runtime_location_and_clean_api(monkeypatch, tmp_path):
    state_path = tmp_path / "current_port_state.parquet"
    disruptions_path = tmp_path / "current_disruptions.parquet"
    affected_path = tmp_path / "disruption_affected_ports.parquet"
    mapping_path = tmp_path / "runtime_location_mapping.csv"
    pd.DataFrame(
        [
            {
                "location_id": "PW_PORT_port1201",
                "source_port_id": "port1201",
                "latest_observation_date": date(2026, 8, 14),
                "activity_score": 1.0,
                "activity_anomaly_score": -0.07,
                "operational_status": "HIGH_ACTIVITY",
                "source": "PORTWATCH",
            }
        ]
    ).to_parquet(state_path, index=False)
    pd.DataFrame(
        [
            {
                "event_id": "PW-1",
                "event_type": "PORT_CONGESTION",
                "event_name": "Singapore activity signal",
                "description": "Test PortWatch event",
                "alert_level": "AMBER",
                "severity_text": "Test",
                "start_time": "2026-08-14T00:00:00Z",
                "end_time": None,
            }
        ]
    ).to_parquet(disruptions_path, index=False)
    pd.DataFrame(
        [{"event_id": "PW-1", "location_id": "PW_PORT_port1201"}]
    ).to_parquet(affected_path, index=False)
    mapping_path.write_text(
        "runtime_location_id,canonical_location_id\nP_SG,PW_PORT_port1201\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "portwatch_state_path", str(state_path))
    monkeypatch.setattr(settings, "portwatch_disruptions_path", str(disruptions_path))
    monkeypatch.setattr(settings, "portwatch_affected_ports_path", str(affected_path))
    monkeypatch.setattr(settings, "runtime_location_mapping_path", str(mapping_path))

    with TestClient(app) as client:
        location = client.get("/locations/P_SG")
        state = client.get("/portwatch/state")
        disruptions = client.get("/portwatch/disruptions")
        impacts = client.get("/portwatch/impacts")

    assert location.status_code == 200
    assert location.json()["source"] == "PORTWATCH"
    assert location.json()["canonical_location_id"] == "PW_PORT_port1201"
    assert location.json()["latest_observation_date"] == "2026-08-14"
    assert location.json()["activity_score"] == 1.0
    assert location.json()["operational_status"] == "HIGH_ACTIVITY"
    assert state.json()["P_SG"]["canonical_location_id"] == "PW_PORT_port1201"
    assert disruptions.json()[0]["affected_location_ids"] == ["PW_PORT_port1201"]
    assert impacts.status_code == 200
    assert impacts.json()[0]["affected_location"] == "LOC_WPI_50000"
    assert impacts.json()[0]["affected_shipments"]


def test_local_react_origin_supports_cors_preflight():
    with TestClient(app) as client:
        preflight = client.options(
            "/locations",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        response = client.get(
            "/locations",
            headers={"Origin": "http://localhost:5173"},
        )
        unlisted = client.get(
            "/locations",
            headers={"Origin": "https://unlisted.example"},
        )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in unlisted.headers


def test_simulation_contract():
    with TestClient(app) as client:
        response=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72})
        assert response.status_code==200
        assert response.json()["affected_shipments"]
        disruption_id = response.json()["disruption_id"]
    with Session() as session:
        affected_locations = session.scalars(
            select(DisruptionLocationRecord.location_id).where(
                DisruptionLocationRecord.disruption_id == disruption_id
            )
        ).all()
        assert list(affected_locations) == ["LOC_WPI_50000"]
        assert session.get(SimulationRunRecord, disruption_id) is not None


def test_simulation_rejects_unknown_database_references():
    with TestClient(app) as client:
        response = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["P_UNKNOWN"],
                "duration_hours": 72,
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["unknown_location_ids"] == ["P_UNKNOWN"]


def test_reroute_reuses_simulation_record(monkeypatch):
    """A reroute must update its simulation row rather than insert a duplicate ID."""
    with TestClient(app) as client:
        simulation=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72}).json()
        # Explanation generation is separately tested/mocked; persistence is the behavior under test here.
        monkeypatch.setattr("backend.app.main.explain",lambda record: {"summary":"ok","recommended_action":"act","reasoning_summary":"grounded","delay_saved_hours":record["delay_saved_hours"],"additional_cost":record["additional_cost"],"risk_warning":"","next_steps":[]})
        response=client.post(f"/reroute?disruption_id={simulation['disruption_id']}")
        assert response.status_code==200
        recommendations = response.json()["recommendations"]
    with Session() as session:
        decision_count = session.scalar(
            select(func.count())
            .select_from(AgentDecisionRecord)
            .where(
                AgentDecisionRecord.disruption_id
                == simulation["disruption_id"]
            )
        )
        assert decision_count == len(recommendations)
        run = session.get(SimulationRunRecord, simulation["disruption_id"])
        assert run is not None
        assert run.reroute_result is not None


def test_shipment_analytics_is_on_demand(monkeypatch):
    with TestClient(app) as client:
        simulation=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72}).json()
        batch=client.post(f"/reroute?disruption_id={simulation['disruption_id']}").json()
        shipment_id=batch["recommendations"][0]["shipment_id"]
        monkeypatch.setattr("backend.app.main.explain",lambda record: {"summary":"ok","recommended_action":"act","reasoning_summary":"grounded","delay_saved_hours":record["delay_saved_hours"],"additional_cost":record["additional_cost"],"risk_warning":"","next_steps":[]})
        response=client.post("/shipment-analytics",json={"disruption_id":simulation["disruption_id"],"shipment_id":shipment_id})
        assert response.status_code==200
        assert response.json()["shipment_id"]==shipment_id


def test_interactive_plan_uses_labeled_offline_explanation(monkeypatch):
    from backend.app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        response = client.post(
            "/plan-route",
            json={
                "origin_id": "F_SZ",
                "destination_id": "C_A",
                "disruption": {
                    "disruption_type": "PORT_CLOSURE",
                    "affected_location_ids": ["P_SG"],
                    "duration_hours": 72,
                },
                "generate_explanation": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["explanation"]["source"] == "offline_deterministic"


def test_interactive_plan_falls_back_when_provider_is_unreachable(monkeypatch):
    from openai import APIConnectionError
    from backend.app.config import settings

    class FailingResponses:
        def create(self, **kwargs):
            raise APIConnectionError(request=None)

    class FailingClient:
        def __init__(self, **kwargs):
            self.responses = FailingResponses()

    monkeypatch.setattr(settings, "openai_api_key", "configured-for-test")
    monkeypatch.setattr("backend.app.llm.OpenAI", FailingClient)
    with TestClient(app) as client:
        response = client.post(
            "/plan-route",
            json={
                "origin_id": "F_SZ",
                "destination_id": "C_A",
                "disruption": {
                    "disruption_type": "PORT_CLOSURE",
                    "affected_location_ids": ["P_SG"],
                    "duration_hours": 72,
                },
                "generate_explanation": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ROUTE_FOUND"
    assert response.json()["explanation"]["fallback_reason"] == "provider_unavailable"


def test_recommendations_include_disruption_inputs():
    with TestClient(app) as client:
        client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["P_SG"],
                "duration_hours": 72,
            },
        )
        response = client.get("/recommendations")

    assert response.status_code == 200
    assert response.json()
    assert response.json()[-1]["disruption"]["affected_location_ids"] == ["LOC_WPI_50000"]


def test_dashboard_assistant_answers_from_current_context(monkeypatch):
    from backend.app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        response = client.post(
            "/assistant",
            json={
                "question": "Which customers are affected most?",
                "context": {
                    "locations": {"C_A": "Customer A", "C_B": "Customer B"},
                    "affected_shipments": [
                        {"id": "S001", "destination_id": "C_A", "priority": "HIGH"},
                        {"id": "S002", "destination_id": "C_A", "priority": "MEDIUM"},
                        {"id": "S003", "destination_id": "C_B", "priority": "LOW"},
                    ],
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["source"] == "offline_deterministic"
    assert "Customer A" in response.json()["answer"]


def test_assistant_reconstructs_context_from_simulation_id(monkeypatch):
    from backend.app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        simulation = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["P_SG"],
                "duration_hours": 72,
            },
        ).json()
        response = client.post(
            "/assistant",
            json={
                "question": "Which customers are affected most?",
                "simulation_run_id": simulation["disruption_id"],
                "context": {
                    "locations": {"C_A": "Invented browser location"},
                    "affected_shipments": [
                        {"id": "FAKE", "destination_id": "C_A", "priority": "HIGH"}
                    ],
                },
            },
        )

    assert response.status_code == 200
    assert "Asia Customer Market" in response.json()["answer"]
    assert "Invented browser location" not in response.json()["answer"]
