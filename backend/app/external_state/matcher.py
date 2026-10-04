"""Deterministic matching from one external signal to network metadata."""

from __future__ import annotations

from ..domain import Location, Route
from .geospatial import match_route_sample_points
from .schemas import (
    ExternalSignal,
    NetworkMatchType,
    SignalNetworkMatch,
    RouteMatchEvidence,
    SignalTargetType,
)


DEFAULT_GEO_RADIUS_KM = 100.0


def match_signal_to_network(
    signal: ExternalSignal,
    locations: list[Location],
    routes: list[Route],
    *,
    default_radius_km: float = DEFAULT_GEO_RADIUS_KM,
) -> SignalNetworkMatch:
    """Match explicit targets and representative route exposure points.

    Location matching accepts runtime IDs, canonical IDs, and UN/LOCODEs. It
    does not infer downstream locations; shipment exposure performs that
    remaining-leg intersection separately.
    """

    route_by_id = {route.route_id: route for route in routes}
    affected_locations: set[str] = set()
    affected_routes: set[str] = set()
    matched_corridors: set[str] = set()
    evidence: list[RouteMatchEvidence] = []

    if signal.target_type == SignalTargetType.LOCATION and signal.target_id:
        matched_location_ids = {
            location.location_id
            for location in locations
            if signal.target_id
            in {
                location.location_id,
                location.canonical_location_id,
                location.unlocode,
            }
        }
        affected_locations.update(matched_location_ids)
        for route in routes:
            if (
                route.source_location_id in matched_location_ids
                or route.destination_location_id in matched_location_ids
            ):
                affected_routes.add(route.route_id)
                evidence.append(
                    RouteMatchEvidence(
                        route_id=route.route_id,
                        match_type=NetworkMatchType.LOCATION,
                    )
                )

    if signal.target_type == SignalTargetType.ROUTE and signal.target_id:
        route = route_by_id.get(signal.target_id)
        if route is not None:
            affected_routes.add(route.route_id)
            evidence.append(
                RouteMatchEvidence(
                    route_id=route.route_id,
                    match_type=NetworkMatchType.ROUTE,
                )
            )

    if signal.target_type == SignalTargetType.CORRIDOR and signal.target_id:
        if any(signal.target_id in route.corridor_ids for route in routes):
            matched_corridors.add(signal.target_id)
        for route in routes:
            if signal.target_id not in route.corridor_ids:
                continue
            affected_routes.add(route.route_id)
            evidence.append(
                RouteMatchEvidence(
                    route_id=route.route_id,
                    match_type=NetworkMatchType.CORRIDOR,
                    matched_corridor_id=signal.target_id,
                )
            )

    if signal.latitude is not None and signal.longitude is not None:
        radius_km = signal.radius_km or default_radius_km
        for sample_match in match_route_sample_points(
            routes,
            signal.latitude,
            signal.longitude,
            radius_km,
        ):
            affected_routes.add(sample_match.route_id)
            evidence.append(
                RouteMatchEvidence(
                    route_id=sample_match.route_id,
                    match_type=NetworkMatchType.GEO,
                    sample_point_sequences=[sample_match.sequence],
                    distances_km=[sample_match.distance_km],
                )
            )

    deduplicated_evidence = _merge_evidence(evidence)
    return SignalNetworkMatch(
        signal_id=signal.id,
        affected_locations=sorted(affected_locations),
        affected_routes=sorted(affected_routes),
        matched_corridors=sorted(matched_corridors),
        route_evidence=deduplicated_evidence,
    )


def _merge_evidence(evidence: list[RouteMatchEvidence]) -> list[RouteMatchEvidence]:
    merged: dict[tuple[str, NetworkMatchType, str | None], RouteMatchEvidence] = {}
    for item in evidence:
        key = (item.route_id, item.match_type, item.matched_corridor_id)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        existing.sample_point_sequences = sorted(
            set(existing.sample_point_sequences) | set(item.sample_point_sequences)
        )
        existing.distances_km = sorted(
            set(existing.distances_km) | set(item.distances_km)
        )
    return sorted(
        merged.values(),
        key=lambda item: (
            item.route_id,
            item.match_type.value,
            item.matched_corridor_id or "",
        ),
    )
