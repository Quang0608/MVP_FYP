import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.data_pipeline.validate_data import (
    CanonicalLocation,
    CanonicalRoute,
    validate_dataset,
)
from backend.data_pipeline import validate_data


ROOT = Path(__file__).resolve().parents[2]


def read_sample(filename: str, nullable: set[str] | None = None) -> list[dict[str, str | None]]:
    nullable = nullable or set()
    path = ROOT / "data" / "samples" / filename
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {key: (None if key in nullable and value == "" else value) for key, value in row.items()}
        for row in rows
    ]


def test_all_sample_datasets_validate_together():
    locations = [
        CanonicalLocation.model_validate(row)
        for row in read_sample("locations_sample.csv", {"unlocode"})
    ]
    routes = [CanonicalRoute.model_validate(row) for row in read_sample("routes_sample.csv")]
    shipments = [
        validate_data.CanonicalShipment.model_validate(row)
        for row in read_sample("shipments_sample.csv", {"vessel_id"})
    ]
    route_steps = [
        validate_data.CanonicalShipmentRouteStep.model_validate(row)
        for row in read_sample("shipment_route_steps_sample.csv")
    ]
    vessels = [
        validate_data.CanonicalVessel.model_validate(row)
        for row in read_sample("vessels_sample.csv")
    ]
    positions = [
        validate_data.CanonicalVesselPosition.model_validate(row)
        for row in read_sample("vessel_positions_sample.csv")
    ]
    metrics = [
        validate_data.CanonicalPortMetrics.model_validate(row)
        for row in read_sample("port_metrics_sample.csv")
    ]
    events = [
        validate_data.CanonicalDisruptionEvent.model_validate(row)
        for row in read_sample("disruption_events_sample.csv", {"location_id", "route_id"})
    ]

    dataset = validate_dataset(
        locations=locations,
        routes=routes,
        shipments=shipments,
        shipment_route_steps=route_steps,
        vessels=vessels,
        vessel_positions=positions,
        port_metrics=metrics,
        disruption_events=events,
    )

    assert len(dataset.locations) == 6
    assert len(dataset.routes) == 6
    assert len(dataset.shipments) == 2
    assert len(dataset.disruption_events) == 2


def test_invalid_location_coordinates_are_rejected():
    with pytest.raises(ValidationError):
        CanonicalLocation(
            location_id="LOC_BAD",
            name="Invalid",
            location_type="PORT",
            country="Singapore",
            city="Singapore",
            latitude=91,
            longitude=103.8,
            capacity=1,
            status="ACTIVE",
            source="TEST",
        )


def test_unknown_route_reference_is_rejected():
    location = CanonicalLocation(
        location_id="LOC_A",
        name="A",
        location_type="FACTORY",
        country="Singapore",
        city="Singapore",
        latitude=1,
        longitude=103,
        capacity=1,
        status="ACTIVE",
        source="TEST",
    )
    route = CanonicalRoute(
        route_id="R_BAD",
        source_location_id="LOC_A",
        destination_location_id="LOC_UNKNOWN",
        transport_mode="ROAD",
        distance_km=1,
        base_duration_hours=1,
        base_cost=1,
        max_capacity=1,
        risk_score=0,
        status="ACTIVE",
    )

    with pytest.raises(ValidationError, match="unknown destination location"):
        validate_dataset(locations=[location], routes=[route], shipments=[])
