"""External signal to exposed-shipment orchestration.

This service stops at evidence. It does not construct a NetworkState overlay,
change route weights, classify operational impact, or invoke rerouting.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ..domain import Location, Route, Shipment, ShipmentRouteLeg
from .matcher import match_signal_to_network
from .schemas import (
    ExternalExposureResult,
    ExternalSignal,
    NetworkMatchType,
    RouteMatchEvidence,
    SignalNetworkMatch,
    ShipmentExposure,
)
from .temporal import estimate_remaining_leg_windows, signal_overlaps_window


def find_shipments_exposed(
    signal: ExternalSignal,
    shipments: list[Shipment],
    routes: list[Route],
    locations: list[Location] | None = None,
    *,
    reference_time: datetime | None = None,
    default_radius_km: float = 100.0,
) -> ExternalExposureResult:
    """Return remaining shipment legs with spatial and temporal overlap."""

    locations = locations or []
    network_match = match_signal_to_network(
        signal,
        locations,
        routes,
        default_radius_km=default_radius_km,
    )
    evidence_by_route: dict[str, list[RouteMatchEvidence]] = defaultdict(list)
    for evidence in network_match.route_evidence:
        evidence_by_route[evidence.route_id].append(evidence)

    exposures: list[ShipmentExposure] = []
    for shipment in shipments:
        remaining_legs = shipment.remaining_route_legs()
        if not remaining_legs:
            continue
        remaining_locations = {shipment.current_location_id}
        remaining_locations.update(
            leg.destination_location_id for leg in remaining_legs
        )
        windows = {
            window.route_id: window
            for window in estimate_remaining_leg_windows(
                shipment,
                routes,
                reference_time,
            )
        }
        for leg in remaining_legs:
            window = windows.get(leg.route_id)
            if window is None:
                continue
            matches = _leg_matches(
                signal,
                leg,
                remaining_locations,
                network_match,
                evidence_by_route,
            )
            if not matches or not signal_overlaps_window(
                signal,
                window.estimated_entry_time,
                window.estimated_exit_time,
            ):
                continue
            for (
                match_type,
                matched_location_id,
                matched_corridor_id,
                sequences,
                distances,
            ) in matches:
                exposures.append(
                    ShipmentExposure(
                        shipment_id=shipment.shipment_id,
                        route_id=leg.route_id,
                        sequence=leg.sequence_no,
                        match_type=match_type,
                        spatial_match=True,
                        temporal_match=True,
                        estimated_entry_time=window.estimated_entry_time,
                        estimated_exit_time=window.estimated_exit_time,
                        matched_location_id=matched_location_id,
                        matched_corridor_id=matched_corridor_id,
                        matched_sample_point_sequences=sequences,
                        distances_km=distances,
                    )
                )
    return ExternalExposureResult(
        signal=signal,
        network_match=network_match,
        exposed_shipments=sorted(
            exposures,
            key=lambda item: (item.shipment_id, item.sequence, item.route_id),
        ),
    )


def _leg_matches(
    signal: ExternalSignal,
    leg: ShipmentRouteLeg,
    remaining_locations: set[str],
    network_match: SignalNetworkMatch,
    evidence_by_route: dict[str, list[RouteMatchEvidence]],
) -> list[tuple[NetworkMatchType, str | None, str | None, list[int], list[float]]]:
    if signal.target_type.value == "LOCATION":
        matched_locations = set(network_match.affected_locations) & remaining_locations
        if not matched_locations or (
            leg.source_location_id not in matched_locations
            and leg.destination_location_id not in matched_locations
        ):
            return []
        return [
            (NetworkMatchType.LOCATION, location_id, None, [], [])
            for location_id in sorted(matched_locations)
            if location_id in {leg.source_location_id, leg.destination_location_id}
        ]

    route_evidence = evidence_by_route.get(leg.route_id, [])
    if not route_evidence:
        return []
    matches = []
    for evidence in route_evidence:
        matches.append(
            (
                evidence.match_type,
                None,
                evidence.matched_corridor_id,
                evidence.sample_point_sequences,
                evidence.distances_km,
            )
        )
    return matches
