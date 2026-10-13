import os
from datetime import datetime, timezone

os.environ["DATABASE_URL"] = "sqlite://"

import networkx as nx
import pytest

from backend.app.domain import Location, LocationType, Route, RuntimeDataset, Status
from backend.app.persistence.neo4j.projection import (
    Neo4jProjectionError,
    project_dataset,
)
from backend.app.persistence.neo4j.parity import _compare_records, _model_records
from backend.app.persistence.neo4j.repository import Neo4jReadRepository


class FakeManager:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute_read(self, query, parameters):
        self.queries.append((query, parameters))
        if "Route)-[from_rel" in query:
            return self.rows["routes"]
        if "RoutePlan" in query:
            return self.rows["plans"]
        if "ShipmentLeg" in query:
            return self.rows["legs"]
        if "Shipment)" in query:
            return self.rows["shipments"]
        return [{"properties": item} for item in self.rows["locations"]]


def _properties():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "locations": [
            {
                "location_id": "A",
                "name": "A",
                "location_type": "PORT",
                "country": "SG",
                "latitude": 1.0,
                "longitude": 103.0,
                "status": "ACTIVE",
                "source": "SYNTHETIC",
                "capacity": 10.0,
            },
            {
                "location_id": "B",
                "name": "B",
                "location_type": "CUSTOMER",
                "country": "SG",
                "latitude": 1.1,
                "longitude": 103.1,
                "status": "ACTIVE",
                "source": "SYNTHETIC",
                "capacity": 10.0,
            },
        ],
        "routes": [{
            "properties": {
                "route_id": "R1",
                "source_location_id": "A",
                "destination_location_id": "B",
                "transport_mode": "SEA",
                "distance_km": 1.0,
                "base_duration_hours": 2.0,
                "base_cost": 3.0,
                "max_capacity": 10.0,
                "risk_score": 0.1,
                "status": "ACTIVE",
                "current_load": 0.0,
                "source": "SYNTHETIC",
                "corridor_ids": [],
                "weather_sample_points_json": "[]",
            },
            "source_location_id": "A",
            "destination_location_id": "B",
        }],
        "plans": [{"properties": {"plan_id": "S1:v1", "shipment_id": "S1", "plan_version": 1, "active": True}}],
        "legs": [{"properties": {
            "leg_id": "S1:v1:1", "plan_id": "S1:v1", "shipment_id": "S1",
            "sequence_no": 1, "route_id": "R1", "source_location_id": "A",
            "destination_location_id": "B", "status": "CURRENT", "planned_departure": now,
            "planned_arrival": now, "transport_mode": "SEA",
        }}],
        "shipments": [{"properties": {
            "shipment_id": "S1", "origin_location_id": "A", "destination_location_id": "B",
            "current_location_id": "A", "priority": "HIGH", "required_delivery_time": now,
            "current_eta": now, "load_units": 1.0, "cargo_type": "GENERAL", "status": "ON_TIME",
            "order_id": "ORD_S1", "customer_id": "B", "source": "SYNTHETIC",
        }}],
    }


def test_read_repository_returns_canonical_models_and_scope():
    manager = FakeManager(_properties())
    repository = Neo4jReadRepository(manager, snapshot_id="snap", import_scope="scope")

    locations = repository.get_locations()
    routes = repository.get_routes()
    plans = repository.get_route_plans()
    legs = repository.get_shipment_leg_records()
    shipments = repository.get_shipments()

    assert [item.location_id for item in locations] == ["A", "B"]
    assert routes[0].source_location_id == "A"
    assert routes[0].destination_location_id == "B"
    assert plans[0].plan_id == "S1:v1"
    assert legs[0].leg_id == "S1:v1:1"
    assert shipments[0].ordered_route_legs[0].sequence_no == 1
    assert all(
        parameters == {"snapshot_id": "snap", "import_scope": "scope"}
        for _, parameters in manager.queries
    )


def test_projection_uses_existing_directed_graph_builder():
    dataset = RuntimeDataset(
        locations=[
            Location(location_id="A", name="A", location_type=LocationType.PORT, country="SG", latitude=1, longitude=103),
            Location(location_id="B", name="B", location_type=LocationType.CUSTOMER, country="SG", latitude=1, longitude=103),
        ],
        routes=[
            Route(route_id="R1", source_location_id="A", destination_location_id="B", transport_mode="SEA", base_duration_hours=2, base_cost=3, max_capacity=10, risk_score=0.1),
        ],
        shipments=[],
    )
    graph = project_dataset(dataset)
    assert isinstance(graph, nx.DiGraph)
    assert list(graph.edges()) == [("A", "B")]
    assert graph["A"]["B"]["route_id"] == "R1"
    assert graph["A"]["B"]["weight"] == 2


def test_projection_rejects_parallel_routes_before_digraph_collapse():
    dataset = RuntimeDataset(
        locations=[
            Location(location_id="A", name="A", location_type=LocationType.PORT, country="SG", latitude=1, longitude=103),
            Location(location_id="B", name="B", location_type=LocationType.CUSTOMER, country="SG", latitude=1, longitude=103),
        ],
        routes=[
            Route(route_id="R1", source_location_id="A", destination_location_id="B", transport_mode="SEA", base_duration_hours=2, base_cost=3, max_capacity=10, risk_score=0.1),
            Route(route_id="R2", source_location_id="A", destination_location_id="B", transport_mode="AIR", base_duration_hours=1, base_cost=4, max_capacity=10, risk_score=0.1),
        ],
        shipments=[],
    )
    with pytest.raises(Neo4jProjectionError):
        project_dataset(dataset)


def test_parity_harness_uses_stable_ids_and_canonical_records():
    dataset = RuntimeDataset(
        locations=[
            Location(location_id="B", name="B", location_type=LocationType.CUSTOMER, country="SG", latitude=1, longitude=103),
            Location(location_id="A", name="A", location_type=LocationType.PORT, country="SG", latitude=1, longitude=103),
        ],
        routes=[],
        shipments=[],
    )
    records = _model_records(dataset)
    comparison = _compare_records(records["locations"], list(reversed(records["locations"])), "location_id")
    assert [item["location_id"] for item in records["locations"]] == ["A", "B"]
    assert comparison["pass"] is True
