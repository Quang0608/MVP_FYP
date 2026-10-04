"""Deterministic signal-window and shipment traversal-window helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..domain import Route, Shipment
from .schemas import ExternalSignal, ShipmentTraversalWindow


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def windows_overlap(
    first_start: datetime,
    first_end: datetime | None,
    second_start: datetime,
    second_end: datetime | None,
) -> bool:
    """Use inclusive boundaries; an event at leg entry/exit overlaps."""

    first_start = as_utc(first_start)
    second_start = as_utc(second_start)
    first_end = as_utc(first_end) if first_end is not None else None
    second_end = as_utc(second_end) if second_end is not None else None
    first_latest = first_end or datetime.max.replace(tzinfo=timezone.utc)
    second_latest = second_end or datetime.max.replace(tzinfo=timezone.utc)
    return max(first_start, second_start) <= min(first_latest, second_latest)


def signal_overlaps_window(
    signal: ExternalSignal,
    entry_time: datetime,
    exit_time: datetime,
) -> bool:
    return windows_overlap(
        signal.valid_from,
        signal.valid_to,
        entry_time,
        exit_time,
    )


def estimate_remaining_leg_windows(
    shipment: Shipment,
    routes: list[Route],
    reference_time: datetime | None = None,
) -> list[ShipmentTraversalWindow]:
    """Estimate windows from current progress and route-leg schedules.

    Planned leg timestamps are preferred. When they are absent, the first
    available anchor is ``reference_time`` or ``current_eta`` and subsequent
    exits use the deterministic baseline route duration.
    """

    route_by_id = {route.route_id: route for route in routes}
    remaining_legs = shipment.remaining_route_legs()
    if not remaining_legs:
        return []
    first_scheduled_departure = next(
        (
            leg.planned_departure
            for leg in remaining_legs
            if leg.planned_departure is not None
        ),
        None,
    )
    anchor = (
        reference_time
        or first_scheduled_departure
        or shipment.current_eta
        or shipment.required_delivery_time
    )
    cursor = as_utc(anchor)
    windows: list[ShipmentTraversalWindow] = []
    for leg in remaining_legs:
        route = route_by_id.get(leg.route_id)
        if route is None:
            continue
        planned_departure = (
            as_utc(leg.planned_departure)
            if leg.planned_departure is not None
            else None
        )
        planned_arrival = (
            as_utc(leg.planned_arrival)
            if leg.planned_arrival is not None
            else None
        )
        entry = max(cursor, planned_departure) if planned_departure else cursor
        planned_duration = (
            (planned_arrival - planned_departure).total_seconds() / 3600
            if planned_departure and planned_arrival
            else 0
        )
        duration = max(route.base_duration_hours, planned_duration)
        exit_time = entry + timedelta(hours=duration)
        windows.append(
            ShipmentTraversalWindow(
                shipment_id=shipment.shipment_id,
                route_id=leg.route_id,
                sequence=leg.sequence_no,
                estimated_entry_time=entry,
                estimated_exit_time=exit_time,
            )
        )
        cursor = exit_time
    return windows
