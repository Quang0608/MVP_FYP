"""Compatibility normalization for legacy demo identifiers."""

from __future__ import annotations

from .schemas import DisruptionRequest, RoutePlanRequest


LEGACY_LOCATION_ALIASES = {
    "P_SG": "LOC_WPI_50000",
    "P_KL": "LOC_WPI_49930",
    "P_TP": "LOC_WPI_51587",
    "P_LC": "LOC_WPI_57462",
    "F_SZ": "ASIA_F_001",
    "F_HCM": "ASIA_F_003",
    "F_BKK": "ASIA_F_005",
    "C_A": "ASIA_C_001",
    "C_B": "ASIA_C_002",
    "C_C": "ASIA_C_003",
}


def canonical_location_id(location_id: str) -> str:
    return LEGACY_LOCATION_ALIASES.get(location_id, location_id)


def canonical_route_id(route_id: str) -> str:
    if route_id.startswith("ASIA_R_"):
        return route_id
    try:
        return f"ASIA_R_{int(route_id.removeprefix('R')):04}"
    except ValueError:
        return route_id


def canonicalize_disruption_request(request: DisruptionRequest) -> DisruptionRequest:
    return request.model_copy(
        update={
            "affected_location_ids": [
                canonical_location_id(location_id)
                for location_id in request.affected_location_ids
            ],
            "affected_route_ids": [
                canonical_route_id(route_id) for route_id in request.affected_route_ids
            ],
        }
    )


def canonicalize_route_plan_request(request: RoutePlanRequest) -> RoutePlanRequest:
    disruption = (
        canonicalize_disruption_request(request.disruption)
        if request.disruption
        else None
    )
    return request.model_copy(
        update={
            "origin_id": canonical_location_id(request.origin_id),
            "destination_id": canonical_location_id(request.destination_id),
            "disruption": disruption,
        }
    )
