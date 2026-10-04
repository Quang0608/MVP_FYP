import os

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient

from backend.app.agent.schemas import (
    SimulationInput,
    SupervisorRequest,
)
from backend.app.agent.supervisor import SupervisorAgent, run_supervisor
from backend.app.agent.tools.operations import AgentToolError, get_affected_shipments, get_shipment
from backend.app.agent.tools.operations import get_shipment_route, resolve_location
from backend.app.config import settings
from backend.app.main import app
from backend.app.repository import initialise_database


initialise_database()


def test_tool_shipment_and_route_are_repository_grounded():
    shipment = get_shipment("ASIA_S_0021")
    route = get_shipment_route("ASIA_S_0021")

    assert shipment.shipment_id == "ASIA_S_0021"
    assert shipment.origin_location_id
    assert shipment.destination_location_id
    assert shipment.current_location_id
    assert route.shipment_id == shipment.shipment_id
    assert route.legs
    assert [leg.sequence_no for leg in route.legs] == sorted(
        leg.sequence_no for leg in route.legs
    )


def test_unknown_shipment_cannot_produce_operational_facts():
    try:
        get_shipment("NOT-A-SHIPMENT")
    except AgentToolError as exc:
        assert exc.code == "UNKNOWN_SHIPMENT"
    else:
        raise AssertionError("Unknown shipment unexpectedly returned data")


def test_location_resolution_reports_ambiguity():
    resolution = resolve_location("ASIA_F")

    assert resolution.ambiguous is True
    assert resolution.resolved is None
    assert len(resolution.matches) > 1


def test_supervisor_offline_queries_affected_shipments(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        simulation = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["LOC_WPI_50000"],
                "duration_hours": 72,
            },
        ).json()
        response = client.post(
            "/supervisor",
            json={
                "question": "Which high-priority shipments are affected?",
                "simulation_run_id": simulation["disruption_id"],
                "context": {"affected_shipments": [{"id": "FAKE"}]},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "offline_supervisor"
    assert payload["tool_calls"][0]["tool_name"] == "get_simulation"
    assert payload["tool_calls"][1]["tool_name"] == "get_affected_shipments"
    assert payload["state"]["affected_shipments"]
    assert all(
        item["shipment"]["priority"] == "HIGH"
        for item in payload["state"]["affected_shipments"]
    )
    assert "FAKE" not in payload["answer"]


def test_supervisor_explains_one_shipment_from_deterministic_impact(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        simulation = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["LOC_WPI_50000"],
                "duration_hours": 72,
            },
        ).json()
        shipment_id = simulation["affected_shipments"][0]["id"]
        response = client.post(
            "/supervisor",
            json={
                "question": f"Why is {shipment_id} marked reroute required?",
                "shipment_id": shipment_id,
                "simulation_run_id": simulation["disruption_id"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["tool_name"] for item in payload["tool_calls"]] == [
        "get_shipment",
        "get_shipment_impact",
    ]
    assert shipment_id in payload["answer"]
    assert payload["state"]["affected_shipments"][0]["classification"] == "REROUTE_REQUIRED"


def test_supervisor_simulation_uses_same_deterministic_engine_as_dashboard(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    with TestClient(app) as client:
        baseline_routes = client.get("/routes").json()
        direct = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "PORT_CLOSURE",
                "affected_location_ids": ["LOC_WPI_50000"],
                "duration_hours": 72,
            },
        ).json()
        agent_response = client.post(
            "/supervisor",
            json={"question": "Simulate Singapore Port closing for 72 hours."},
        )
        after_routes = client.get("/routes").json()

    assert agent_response.status_code == 200
    agent = agent_response.json()
    assert [item["tool_name"] for item in agent["tool_calls"]] == [
        "resolve_location",
        "simulate_disruption",
        "get_affected_shipments",
    ]
    assert agent["state"]["simulation_run_id"]
    assert agent["state"]["affected_shipments"]
    assert len(agent["state"]["affected_shipments"]) == len(direct["affected_shipments"])
    assert {
        item["shipment"]["shipment_id"]
        for item in agent["state"]["affected_shipments"]
    } == {item["id"] for item in direct["affected_shipments"]}
    assert after_routes == baseline_routes


def test_tool_affected_shipments_matches_deterministic_impact_service():
    with TestClient(app) as client:
        simulation = client.post(
            "/simulate-disruption",
            json={
                "disruption_type": "CONGESTION",
                "affected_location_ids": ["LOC_WPI_49930"],
                "duration_hours": 48,
            },
        ).json()

    result = get_affected_shipments(
        SimulationInput(simulation_run_id=simulation["disruption_id"])
    )
    assert result.total == len(simulation["affected_shipments"])
    assert result.total > 0
    assert all(item.classification.value == "SHIPMENT_AT_RISK" for item in result.shipments)


def test_supervisor_provider_can_call_a_tool_without_live_network(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeResponse:
        def __init__(self, output=None, output_text=""):
            self.output = output or []
            self.output_text = output_text

    class FakeResponses:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(
                    output=[
                        {
                            "type": "function_call",
                            "name": "get_active_disruptions",
                            "arguments": "{}",
                            "call_id": "call-1",
                        }
                    ]
                )
            return FakeResponse(output_text="No active disruptions were returned by the trusted tool.")

    fake_responses = FakeResponses()

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = fake_responses

    monkeypatch.setattr("backend.app.agent.supervisor.OpenAI", FakeClient)
    result = run_supervisor(SupervisorRequest(question="What disruptions are active?"))

    assert result.source == "openai_supervisor"
    assert result.tool_calls[0].tool_name == "get_active_disruptions"
    assert result.tool_calls[0].success is True
    assert fake_responses.calls == 2


def test_supervisor_enforces_tool_iteration_limit(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeResponse:
        output = [
            {
                "type": "function_call",
                "name": "get_active_disruptions",
                "arguments": "{}",
                "call_id": "call-loop",
            }
        ]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr("backend.app.agent.supervisor.OpenAI", FakeClient)
    result = SupervisorAgent(max_tool_iterations=1).run(
        SupervisorRequest(question="What disruptions are active?")
    )

    assert result.source == "supervisor_limit"
    assert len(result.tool_calls) == 1


def test_supervisor_provider_failure_uses_offline_path(monkeypatch):
    from openai import APIConnectionError

    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FailingClient:
        def __init__(self, **kwargs):
            raise APIConnectionError(request=None)

    monkeypatch.setattr("backend.app.agent.supervisor.OpenAI", FailingClient)
    result = run_supervisor(
        SupervisorRequest(question="What disruptions are currently active?")
    )

    assert result.source == "offline_supervisor"
    assert result.fallback_reason == "provider_unavailable"
