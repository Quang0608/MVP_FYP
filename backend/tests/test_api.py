import os
os.environ["DATABASE_URL"]="sqlite://"

from fastapi.testclient import TestClient
from backend.app.main import app


def test_health_and_locations():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"]=="ok"
        assert len(client.get("/locations").json()) >= 13


def test_simulation_contract():
    with TestClient(app) as client:
        response=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72})
        assert response.status_code==200
        assert response.json()["affected_shipments"]


def test_reroute_reuses_simulation_record(monkeypatch):
    """A reroute must update its simulation row rather than insert a duplicate ID."""
    with TestClient(app) as client:
        simulation=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72}).json()
        # Explanation generation is separately tested/mocked; persistence is the behavior under test here.
        monkeypatch.setattr("backend.app.main.explain",lambda record: {"summary":"ok","recommended_action":"act","reasoning_summary":"grounded","delay_saved_hours":record["delay_saved_hours"],"additional_cost":record["additional_cost"],"risk_warning":"","next_steps":[]})
        response=client.post(f"/reroute?disruption_id={simulation['disruption_id']}")
        assert response.status_code==200


def test_shipment_analytics_is_on_demand(monkeypatch):
    with TestClient(app) as client:
        simulation=client.post("/simulate-disruption",json={"disruption_type":"PORT_CLOSURE","affected_location_ids":["P_SG"],"duration_hours":72}).json()
        batch=client.post(f"/reroute?disruption_id={simulation['disruption_id']}").json()
        shipment_id=batch["recommendations"][0]["shipment_id"]
        monkeypatch.setattr("backend.app.main.explain",lambda record: {"summary":"ok","recommended_action":"act","reasoning_summary":"grounded","delay_saved_hours":record["delay_saved_hours"],"additional_cost":record["additional_cost"],"risk_warning":"","next_steps":[]})
        response=client.post("/shipment-analytics",json={"disruption_id":simulation["disruption_id"],"shipment_id":shipment_id})
        assert response.status_code==200
        assert response.json()["shipment_id"]==shipment_id
