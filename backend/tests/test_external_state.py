from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.domain import (
    Location,
    LocationType,
    Priority,
    Route,
    Shipment,
    ShipmentRouteLeg,
    WeatherSamplePoint,
)
from backend.app.external_state.corridors import (
    corridor_memberships_for_route,
    get_network_zones,
)
from backend.app.external_state.geospatial import (
    haversine_km,
    interpolate_weather_sample_points,
)
from backend.app.external_state.matcher import match_signal_to_network
from backend.app.external_state.schemas import (
    ExternalSignal,
    NetworkMatchType,
    OperationalEffect,
    SignalSource,
    SignalStatus,
    SignalTargetType,
    SignalType,
)
from backend.app.external_state.service import find_shipments_exposed
from backend.app.external_state.temporal import (
    estimate_remaining_leg_windows,
    windows_overlap,
)


UTC = timezone.utc


def _location(
    location_id: str,
    latitude: float,
    longitude: float,
    *,
    unlocode: str | None = None,
) -> Location:
    return Location(
        location_id=location_id,
        name=location_id,
        location_type=LocationType.PORT,
        country="Test",
        latitude=latitude,
        longitude=longitude,
        unlocode=unlocode,
    )


def _route(
    route_id: str,
    source: str,
    destination: str,
    *,
    corridors: list[str] | None = None,
    samples: list[WeatherSamplePoint] | None = None,
    duration: float = 12,
) -> Route:
    return Route(
        route_id=route_id,
        source_location_id=source,
        destination_location_id=destination,
        transport_mode="SEA",
        distance_km=300,
        base_duration_hours=duration,
        base_cost=100,
        max_capacity=100,
        risk_score=0.2,
        corridor_ids=corridors or [],
        weather_sample_points=samples or [],
    )


def _shipment(
    shipment_id: str,
    route: Route,
    departure: datetime,
    *,
    status: str = "IN_TRANSIT",
    current_location_id: str | None = None,
    leg_status: str = "CURRENT",
) -> Shipment:
    arrival = departure + timedelta(hours=route.base_duration_hours)
    current_location_id = current_location_id or route.source_location_id
    return Shipment(
        shipment_id=shipment_id,
        origin_location_id=route.source_location_id,
        destination_location_id=route.destination_location_id,
        current_location_id=current_location_id,
        priority=Priority.MEDIUM,
        required_delivery_time=arrival + timedelta(days=1),
        current_eta=arrival,
        load_units=10,
        status=status,
        route_legs=[
            ShipmentRouteLeg(
                shipment_id=shipment_id,
                sequence_no=1,
                route_id=route.route_id,
                source_location_id=route.source_location_id,
                destination_location_id=route.destination_location_id,
                status=leg_status,
                planned_departure=departure,
                planned_arrival=arrival,
                transport_mode=route.transport_mode,
            )
        ],
    )


def _signal(**overrides) -> ExternalSignal:
    values = {
        "id": "SIG-001",
        "source": SignalSource.MANUAL,
        "source_record_id": "fixture-001",
        "signal_type": SignalType.MARINE_WEATHER,
        "target_type": SignalTargetType.GEO_REGION,
        "valid_from": datetime(2026, 9, 28, tzinfo=UTC),
        "valid_to": datetime(2026, 9, 30, tzinfo=UTC),
        "status": SignalStatus.ACTIVE,
    }
    values.update(overrides)
    return ExternalSignal(**values)


def test_external_signal_validation_and_open_ended_window():
    signal = _signal(valid_to=None, confidence=0.8)

    assert signal.valid_to is None
    assert signal.confidence == 0.8

    with pytest.raises(ValidationError):
        _signal(latitude=1.0)

    with pytest.raises(ValidationError):
        _signal(
            valid_from=datetime(2026, 10, 1, tzinfo=UTC),
            valid_to=datetime(2026, 9, 30, tzinfo=UTC),
        )


def test_operational_effect_is_a_validated_future_contract():
    effect = OperationalEffect(
        signal_id="SIG-001",
        target_type=SignalTargetType.ROUTE,
        target_id="R-1",
        available=False,
        valid_from=datetime(2026, 9, 28, tzinfo=UTC),
        reason="Future policy output only",
    )

    assert effect.available is False
    assert effect.duration_multiplier is None


def test_corridor_catalog_and_route_membership_are_deterministic():
    zones = get_network_zones()
    zone_ids = {zone.id for zone in zones}

    assert {"CHK_SUEZ", "CHK_MALACCA", "CHK_HORMUZ"} <= zone_ids
    assert "ZONE_SOUTH_CHINA_SEA" in zone_ids
    assert corridor_memberships_for_route(
        "LOC_WPI_50000",
        "LOC_WPI_48840",
        "SEA",
    ) == [
        "CHK_MALACCA",
        "ZONE_INDIAN_OCEAN",
        "ZONE_RED_SEA",
        "CHK_SUEZ",
    ]
    assert corridor_memberships_for_route("F1", "W1", "ROAD") == []


def test_sample_point_generation_and_haversine_distance():
    source = _location("A", 1.0, 100.0)
    destination = _location("B", 5.0, 104.0)
    points = interpolate_weather_sample_points(source, destination)

    assert len(points) == 5
    assert [point.sequence for point in points] == [1, 2, 3, 4, 5]
    assert points[0].latitude == source.latitude
    assert points[-1].longitude == destination.longitude
    assert haversine_km(1.0, 100.0, 1.0, 100.0) == 0


def test_direct_location_matching_accepts_unlocode_without_inference():
    locations = [_location("LOC_SG", 1.3, 103.8, unlocode="SGSIN"), _location("B", 2, 104)]
    route = _route("R-SG", "A", "LOC_SG", corridors=["CHK_MALACCA"])
    locations.append(_location("A", 0, 103))
    signal = _signal(
        signal_type=SignalType.PORT_CLOSURE,
        target_type=SignalTargetType.LOCATION,
        target_id="SGSIN",
    )

    match = match_signal_to_network(signal, locations, [route])

    assert match.affected_locations == ["LOC_SG"]
    assert match.affected_routes == ["R-SG"]
    assert match.matched_corridors == []
    assert match.route_evidence[0].match_type == NetworkMatchType.LOCATION


def test_corridor_matching_returns_only_tagged_routes():
    locations = [_location("A", 0, 100), _location("B", 1, 101), _location("C", 2, 102)]
    suez_route = _route("R-SUEZ", "A", "B", corridors=["CHK_SUEZ"])
    other_route = _route("R-OTHER", "B", "C", corridors=["CHK_MALACCA"])
    signal = _signal(
        signal_type=SignalType.CORRIDOR_CLOSURE,
        target_type=SignalTargetType.CORRIDOR,
        target_id="CHK_SUEZ",
    )

    match = match_signal_to_network(signal, locations, [suez_route, other_route])

    assert match.affected_routes == ["R-SUEZ"]
    assert match.matched_corridors == ["CHK_SUEZ"]


def test_coordinate_matching_handles_near_and_far_routes():
    locations = [_location("A", 0, 100), _location("B", 1, 101), _location("C", 20, 130)]
    near_route = _route(
        "R-NEAR",
        "A",
        "B",
        samples=[WeatherSamplePoint(latitude=0.5, longitude=100.5, sequence=1)],
    )
    far_route = _route(
        "R-FAR",
        "B",
        "C",
        samples=[WeatherSamplePoint(latitude=20, longitude=130, sequence=1)],
    )
    signal = _signal(latitude=0.5, longitude=100.5, radius_km=10)

    match = match_signal_to_network(signal, locations, [near_route, far_route])

    assert match.affected_routes == ["R-NEAR"]
    assert match.route_evidence[0].sample_point_sequences == [1]


def test_temporal_boundaries_and_open_ended_signals():
    start = datetime(2026, 9, 28, tzinfo=UTC)
    end = datetime(2026, 9, 30, tzinfo=UTC)

    assert windows_overlap(start, end, end, end + timedelta(hours=1))
    assert not windows_overlap(start, end, datetime(2026, 10, 1, tzinfo=UTC), None)
    assert windows_overlap(start, None, datetime(2030, 1, 1, tzinfo=UTC), None)


def test_estimate_remaining_windows_excludes_completed_legs():
    completed = _route("R-DONE", "A", "B", duration=4)
    remaining = _route("R-LEFT", "B", "C", duration=6)
    departure = datetime(2026, 9, 29, tzinfo=UTC)
    shipment = Shipment(
        shipment_id="S-WINDOW",
        origin_location_id="A",
        destination_location_id="C",
        current_location_id="B",
        priority=Priority.MEDIUM,
        required_delivery_time=departure + timedelta(days=2),
        current_eta=departure,
        load_units=10,
        route_legs=[
            ShipmentRouteLeg(
                shipment_id="S-WINDOW",
                sequence_no=1,
                route_id=completed.route_id,
                source_location_id="A",
                destination_location_id="B",
                status="COMPLETED",
                planned_departure=departure - timedelta(hours=4),
                planned_arrival=departure,
            ),
            ShipmentRouteLeg(
                shipment_id="S-WINDOW",
                sequence_no=2,
                route_id=remaining.route_id,
                source_location_id="B",
                destination_location_id="C",
                status="CURRENT",
                planned_departure=departure,
                planned_arrival=departure + timedelta(hours=6),
            ),
        ],
    )

    windows = estimate_remaining_leg_windows(shipment, [completed, remaining])

    assert [window.route_id for window in windows] == ["R-LEFT"]
    assert windows[0].estimated_entry_time == departure


def test_signal_exposure_requires_remaining_route_and_temporal_overlap():
    locations = [_location("A", 0, 100), _location("B", 1, 101), _location("C", 2, 102)]
    route = _route(
        "R-SUEZ",
        "A",
        "B",
        corridors=["CHK_SUEZ"],
        samples=[WeatherSamplePoint(latitude=0.5, longitude=100.5, sequence=1)],
        duration=12,
    )
    future_route = _route("R-FUTURE", "B", "C", duration=4)
    active_departure = datetime(2026, 9, 29, tzinfo=UTC)
    future_departure = datetime(2026, 10, 5, tzinfo=UTC)
    active_shipment = _shipment("S-ACTIVE", route, active_departure)
    future_shipment = _shipment("S-FUTURE", route, future_departure)
    passed_shipment = Shipment(
        shipment_id="S-PASSED",
        origin_location_id="A",
        destination_location_id="C",
        current_location_id="B",
        priority=Priority.MEDIUM,
        required_delivery_time=future_departure + timedelta(days=1),
        current_eta=future_departure,
        load_units=10,
        route_legs=[
            ShipmentRouteLeg(
                shipment_id="S-PASSED",
                sequence_no=1,
                route_id=route.route_id,
                source_location_id="A",
                destination_location_id="B",
                status="COMPLETED",
                planned_departure=active_departure,
                planned_arrival=active_departure + timedelta(hours=12),
            ),
            ShipmentRouteLeg(
                shipment_id="S-PASSED",
                sequence_no=2,
                route_id=future_route.route_id,
                source_location_id="B",
                destination_location_id="C",
                status="CURRENT",
                planned_departure=future_departure,
                planned_arrival=future_departure + timedelta(hours=4),
            ),
        ],
    )
    signal = _signal(
        signal_type=SignalType.CORRIDOR_CLOSURE,
        target_type=SignalTargetType.CORRIDOR,
        target_id="CHK_SUEZ",
    )

    result = find_shipments_exposed(
        signal,
        [active_shipment, future_shipment, passed_shipment],
        [route, future_route],
        locations,
    )

    assert [item.shipment_id for item in result.exposed_shipments] == ["S-ACTIVE"]
    assert result.exposed_shipments[0].match_type == NetworkMatchType.CORRIDOR
    assert result.exposed_shipments[0].spatial_match is True
    assert result.exposed_shipments[0].temporal_match is True
    assert result.network_match.affected_routes == ["R-SUEZ"]


def test_exposure_does_not_change_route_metadata_or_operational_state():
    locations = [_location("A", 0, 100), _location("B", 1, 101)]
    route = _route(
        "R-SEA",
        "A",
        "B",
        corridors=["CHK_SUEZ"],
        samples=[WeatherSamplePoint(latitude=0, longitude=100, sequence=1)],
    )
    before = route.model_copy(deep=True)
    result = find_shipments_exposed(
        _signal(
            signal_type=SignalType.MARINE_WEATHER,
            latitude=0,
            longitude=100,
            radius_km=1,
        ),
        [_shipment("S-1", route, datetime(2026, 9, 29, tzinfo=UTC))],
        [route],
        locations,
    )

    assert result.exposed_shipments
    assert route == before
