"""Compatibility serializers from canonical runtime entities to API DTOs."""

from __future__ import annotations

from ..domain import Location, Route, Shipment
from ..schemas import Location as LocationResponse
from ..schemas import Route as RouteResponse
from ..schemas import Shipment as ShipmentResponse


def location_response(location: Location) -> LocationResponse:
    return LocationResponse(
        id=location.location_id,
        name=location.name,
        type=location.location_type,
        country=location.country,
        latitude=location.latitude,
        longitude=location.longitude,
        capacity=location.capacity,
        status=location.status,
        source=location.source,
        canonical_location_id=location.canonical_location_id,
        portwatch_source_port_id=location.portwatch_source_port_id,
        latest_observation_date=location.latest_observation_date,
        activity_score=location.activity_score,
        activity_anomaly_score=location.activity_anomaly_score,
        operational_status=location.operational_status,
    )


def route_response(route: Route) -> RouteResponse:
    return RouteResponse(
        id=route.route_id,
        source_location_id=route.source_location_id,
        destination_location_id=route.destination_location_id,
        mode=route.transport_mode,
        normal_duration_hours=route.base_duration_hours,
        current_duration_hours=route.current_duration_hours,
        cost=route.base_cost,
        risk_score=route.risk_score,
        capacity=route.max_capacity,
        current_load=route.current_load,
        status=route.status,
        corridor_ids=route.corridor_ids,
        weather_sample_points=route.weather_sample_points,
    )


def shipment_response(shipment: Shipment) -> ShipmentResponse:
    return ShipmentResponse(
        id=shipment.shipment_id,
        origin_id=shipment.origin_location_id,
        destination_id=shipment.destination_location_id,
        current_location_id=shipment.current_location_id,
        planned_route_location_ids=shipment.planned_route_location_ids,
        planned_route_ids=shipment.planned_route_ids,
        deadline=shipment.required_delivery_time,
        priority=shipment.priority,
        load_units=shipment.load_units,
        status=shipment.status,
    )
