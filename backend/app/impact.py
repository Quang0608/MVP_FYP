"""Deterministic shipment impact classification over a network-state overlay."""

from __future__ import annotations

from collections.abc import Iterable

from .domain import DisruptionTargetType, Shipment
from .network_state import NetworkState
from .schemas import ImpactClassification, ShipmentImpact


INACTIVE_SHIPMENT_STATUSES = {"DELIVERED", "CANCELLED", "COMPLETED"}


def classify_shipment_impacts(
    shipments: Iterable[Shipment],
    state: NetworkState,
) -> list[ShipmentImpact]:
    """Classify each shipment using only its current and remaining route."""

    impacts: list[ShipmentImpact] = []
    for shipment in shipments:
        if shipment.status.upper() in INACTIVE_SHIPMENT_STATUSES:
            impacts.append(
                ShipmentImpact(
                    shipment_id=shipment.shipment_id,
                    classification=ImpactClassification.UNAFFECTED,
                    reason="shipment is inactive",
                )
            )
            continue

        remaining_legs = shipment.remaining_route_legs()
        remaining_destination_ids = {
            leg.destination_location_id for leg in remaining_legs
        }
        remaining_route_ids = {leg.route_id for leg in remaining_legs}
        events_by_id = {event.disruption_id: event for event in state.disruptions}
        affected_location_ids: set[str] = set()
        applicable_location_disruption_ids: set[str] = set()
        for location_id, node in state.nodes.items():
            for disruption_id in node.disruption_ids:
                event = events_by_id.get(disruption_id)
                if event is None or not _location_event_applies(
                    event.event_type,
                    location_id,
                    shipment,
                    remaining_destination_ids,
                ):
                    continue
                affected_location_ids.add(location_id)
                applicable_location_disruption_ids.add(disruption_id)

        applicable_route_disruption_ids = {
            event.disruption_id
            for event in state.disruptions
            if event.target_type == DisruptionTargetType.ROUTE
        }
        affected_locations = sorted(affected_location_ids)
        affected_routes = [
            route_id
            for route_id in remaining_route_ids
            if route_id in state.edges
            and any(
                disruption_id in applicable_location_disruption_ids
                or disruption_id in applicable_route_disruption_ids
                for disruption_id in state.edges[route_id].disruption_ids
            )
        ]
        disruption_ids = sorted(
            {
                disruption_id
                for location_id in affected_locations
                for disruption_id in state.nodes[location_id].disruption_ids
            }
            | {
                disruption_id
                for route_id in affected_routes
                for disruption_id in state.edges[route_id].disruption_ids
            }
        )

        if not disruption_ids:
            impacts.append(
                ShipmentImpact(
                    shipment_id=shipment.shipment_id,
                    classification=ImpactClassification.UNAFFECTED,
                    reason="no disruption intersects the remaining route",
                )
            )
            continue

        remaining_edges = [
            state.edges[leg.route_id]
            for leg in remaining_legs
            if leg.route_id in state.edges
        ]
        relevant_edges = [
            edge
            for edge in remaining_edges
            if any(
                disruption_id in applicable_location_disruption_ids
                or disruption_id in applicable_route_disruption_ids
                for disruption_id in edge.disruption_ids
            )
        ]
        unavailable = any(
            not state.nodes[location_id].available
            for location_id in affected_locations
        ) or any(not edge.available for edge in relevant_edges)
        capacity_feasible = all(
            edge.current_load + shipment.load_units <= edge.effective_capacity
            for edge in remaining_edges
        )
        baseline_duration = sum(edge.base_duration for edge in remaining_edges)
        effective_duration = sum(edge.effective_duration for edge in remaining_edges)
        baseline_risk = _average(edge.base_risk for edge in remaining_edges)
        effective_risk = _average(edge.effective_risk for edge in remaining_edges)
        degraded = any(
            edge.effective_duration > edge.base_duration
            or edge.effective_risk > edge.base_risk
            or edge.effective_capacity < edge.base_capacity
            for edge in relevant_edges
        )

        if unavailable or not capacity_feasible:
            classification = ImpactClassification.REROUTE_REQUIRED
            reason = (
                "remaining route is unavailable"
                if unavailable
                else "remaining route lacks effective capacity"
            )
        elif degraded:
            classification = ImpactClassification.SHIPMENT_AT_RISK
            reason = "remaining route remains feasible but network state degraded"
        else:
            classification = ImpactClassification.NETWORK_WARNING
            reason = "relevant disruption is present but route feasibility is unchanged"

        impacts.append(
            ShipmentImpact(
                shipment_id=shipment.shipment_id,
                classification=classification,
                reason=reason,
                disruption_ids=disruption_ids,
                affected_location_ids=sorted(affected_locations),
                affected_route_ids=sorted(affected_routes),
                route_feasible=capacity_feasible and not unavailable,
                baseline_duration_hours=baseline_duration,
                effective_duration_hours=effective_duration,
                baseline_risk_score=baseline_risk,
                effective_risk_score=effective_risk,
            )
        )
    return impacts


def reroute_required_shipments(
    shipments: Iterable[Shipment],
    state: NetworkState,
) -> tuple[list[Shipment], list[ShipmentImpact]]:
    shipments = list(shipments)
    impacts = classify_shipment_impacts(shipments, state)
    shipments_by_id = {shipment.shipment_id: shipment for shipment in shipments}
    required = [
        shipments_by_id[impact.shipment_id]
        for impact in impacts
        if impact.classification == ImpactClassification.REROUTE_REQUIRED
    ]
    return required, impacts


def _average(values: Iterable[float]) -> float | None:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def _location_event_applies(
    event_type: str,
    location_id: str,
    shipment: Shipment,
    remaining_destination_ids: set[str],
) -> bool:
    """Treat a passed current node differently from a required destination.

    A shipment at a port has already passed that port for port-closure purposes;
    a shutdown at its current factory or warehouse still prevents departure.
    The shipment origin is also still an active dependency until its first leg
    has departed.
    """

    if location_id in remaining_destination_ids:
        return True
    if location_id != shipment.current_location_id:
        return False
    if location_id == shipment.origin_location_id:
        return True
    return event_type.upper() in {"FACTORY_SHUTDOWN", "WAREHOUSE_SHUTDOWN"}
