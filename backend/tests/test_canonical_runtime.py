from datetime import date

import pandas as pd

from backend.app.data import seed_data
from backend.app.domain import Location, LocationType, Status
from backend.app.graph import build_supply_chain_graph
from backend.app.integrations.portwatch import PortWatchAdapter
from backend.app.integrations.canonical import locations_from_port_master
from backend.app.schemas import DisruptionRequest, DisruptionType
from backend.app.services import find_affected_shipments


def test_synthetic_seed_loads_as_canonical_runtime_entities():
    locations, routes, shipments = seed_data()

    assert all(isinstance(location, Location) for location in locations)
    assert all(location.location_id == location.id for location in locations)
    assert {location.location_type for location in locations} == {
        LocationType.FACTORY,
        LocationType.PORT,
        LocationType.WAREHOUSE,
        LocationType.CUSTOMER,
    }
    assert all(route.route_id == route.id for route in routes)
    assert all(shipment.shipment_id == shipment.id for shipment in shipments)
    assert all(shipment.route_legs for shipment in shipments)


def test_shipment_route_legs_are_ordered_and_have_progress_state():
    _, _, shipments = seed_data()
    shipment = shipments[0]

    assert [leg.sequence_no for leg in shipment.ordered_route_legs] == [1, 2, 3]
    assert [leg.route_id for leg in shipment.ordered_route_legs] == ["R1", "R9", "R12"]
    assert shipment.ordered_route_legs[0].status == "CURRENT"
    assert all(leg.status == "PLANNED" for leg in shipment.ordered_route_legs[1:])


def test_remaining_route_uses_current_location_and_excludes_completed_legs():
    _, _, shipments = seed_data()
    shipment = shipments[0]
    passed_singapore = shipment.model_copy(update={"current_location_id": "W_SG"})

    assert shipment.remaining_route_ids() == ["R1", "R9", "R12"]
    assert passed_singapore.remaining_route_ids() == ["R12"]
    assert passed_singapore.remaining_route_location_ids() == ["W_SG", "C_A"]


def test_explicit_completed_current_and_planned_leg_states_are_preserved():
    _, _, shipments = seed_data()
    shipment = shipments[0]
    states = ["COMPLETED", "CURRENT", "PLANNED"]
    legs = [
        leg.model_copy(update={"status": status})
        for leg, status in zip(shipment.ordered_route_legs, states, strict=True)
    ]
    progressed = shipment.model_copy(
        update={"current_location_id": "P_SG", "route_legs": legs}
    )

    assert [leg.status for leg in progressed.ordered_route_legs] == states
    assert progressed.remaining_route_ids() == ["R9", "R12"]


def test_impact_detection_uses_remaining_location_and_route_legs():
    _, _, shipments = seed_data()
    shipment = shipments[0]
    singapore_closure = DisruptionRequest(
        disruption_type=DisruptionType.PORT_CLOSURE,
        affected_location_ids=["P_SG"],
        duration_hours=72,
    )
    road_block = DisruptionRequest(
        disruption_type=DisruptionType.ROUTE_BLOCKED,
        affected_route_ids=["R9"],
        duration_hours=24,
    )

    assert find_affected_shipments([shipment], singapore_closure) == [shipment]
    assert find_affected_shipments(
        [shipment.model_copy(update={"current_location_id": "W_SG"})],
        singapore_closure,
    ) == []
    assert find_affected_shipments([shipment], road_block) == [shipment]
    assert find_affected_shipments(
        [shipment.model_copy(update={"current_location_id": "W_SG"})],
        road_block,
    ) == []
    assert find_affected_shipments([shipments[1]], singapore_closure) == []


def test_graph_consumes_canonical_records_and_exposes_scenario_state():
    locations, routes, _ = seed_data()
    graph = build_supply_chain_graph(locations, routes)
    edge = graph["F_SZ"]["P_SG"]

    assert edge["route_id"] == "R1"
    assert edge["duration"] == 48
    assert edge["cost"] == 900
    assert edge["risk"] == 0.2
    assert edge["capacity"] == 100
    assert edge["current_load"] == 20
    assert edge["status"] == Status.ACTIVE


def test_portwatch_mapping_enriches_the_same_canonical_location_model(tmp_path):
    state_path = tmp_path / "current_port_state.parquet"
    mapping_path = tmp_path / "runtime_location_mapping.csv"
    pd.DataFrame(
        [
            {
                "location_id": "PW_PORT_port1201",
                "source_port_id": "port1201",
                "latest_observation_date": date(2026, 8, 14),
                "activity_score": 1.0,
                "activity_anomaly_score": 0.2,
                "operational_status": "HIGH_ACTIVITY",
                "source": "PORTWATCH",
            }
        ]
    ).to_parquet(state_path, index=False)
    mapping_path.write_text(
        "runtime_location_id,canonical_location_id\nP_SG,PW_PORT_port1201\n",
        encoding="utf-8",
    )
    adapter = PortWatchAdapter(
        state_path=state_path,
        disruptions_path=tmp_path / "missing-disruptions.parquet",
        affected_ports_path=tmp_path / "missing-affected.parquet",
        runtime_mapping_path=mapping_path,
    )

    locations, _, _ = seed_data()
    enriched = adapter.enrich_locations(locations)
    singapore = next(location for location in enriched if location.location_id == "P_SG")

    assert isinstance(singapore, Location)
    assert singapore.source == "PORTWATCH"
    assert singapore.canonical_location_id == "PW_PORT_port1201"
    assert singapore.latest_observation_date == date(2026, 8, 14)
    assert singapore.location_type == LocationType.PORT


def test_port_master_adapter_preserves_wpi_identity_and_skips_unresolved_geometry():
    locations = locations_from_port_master(
        [
            {
                "location_id": "LOC_WPI_1",
                "name": "WPI Port",
                "location_type": "PORT",
                "country": "Singapore",
                "latitude": 1.2,
                "longitude": 103.8,
                "unlocode": "SGSIN",
                "canonical_source": "WPI",
                "source_entity_id": "1",
            },
            {
                "location_id": "PW_PORT_native",
                "name": "PortWatch Native",
                "location_type": "PORT",
                "country": "Japan",
                "latitude": None,
                "longitude": None,
                "canonical_source": "PORTWATCH",
                "source_entity_id": "native",
            },
        ]
    )

    assert [location.location_id for location in locations] == ["LOC_WPI_1"]
    assert locations[0].source == "WPI"
    assert locations[0].unlocode == "SGSIN"
