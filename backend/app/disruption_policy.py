"""Canonical disruption normalization and deterministic policy configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .domain import (
    Disruption as CanonicalDisruption,
    DisruptionLifecycleStatus,
    DisruptionTargetType,
)
from .schemas import DisruptionRequest, DisruptionType


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class DisruptionPolicyConfig:
    """Project-defined assumptions applied to external or simulated facts."""

    congestion_duration_multiplier: float = 1.5
    congestion_risk_penalty: float = 0.15
    congestion_current_load_multiplier: float = 1.5
    congestion_capacity_multiplier: float = 1.0
    capacity_reduction_by_severity: dict[str, float] = field(
        default_factory=lambda: {
            "LOW": 0.10,
            "MEDIUM": 0.25,
            "HIGH": 0.50,
            "CRITICAL": 0.75,
        }
    )

    def capacity_reduction_fraction(self, severity: str) -> float:
        return self.capacity_reduction_by_severity.get(severity.upper(), 0.25)


def _parse_datetime(value: Any, default: datetime) -> datetime:
    if value is None or value == "":
        return default
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _canonical_event_type(value: Any) -> str:
    normalized = str(value or "NETWORK_WARNING").upper()
    if normalized == DisruptionType.MULTIPLE_PORT.value:
        return DisruptionType.PORT_CLOSURE.value
    if normalized in {"ROUTE_BLOCKAGE", DisruptionType.ROUTE_BLOCKED.value}:
        return DisruptionType.ROUTE_CLOSURE.value
    if normalized in {"PORT_CONGESTION", "CONGESTION"}:
        return DisruptionType.CONGESTION.value
    return normalized


def canonical_disruptions_from_request(
    request: DisruptionRequest,
    *,
    disruption_id: str = "SIMULATED",
    source: str = "SIMULATED",
    start_time: datetime | None = None,
) -> list[CanonicalDisruption]:
    """Expand a multi-target API request into canonical target events."""

    start = start_time or EPOCH
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    event_type = _canonical_event_type(request.disruption_type.value)
    targets = [
        (DisruptionTargetType.LOCATION, location_id)
        for location_id in request.affected_location_ids
    ]
    targets.extend(
        (DisruptionTargetType.ROUTE, route_id)
        for route_id in request.affected_route_ids
    )
    end = start + timedelta(hours=request.duration_hours)
    return [
        CanonicalDisruption(
            disruption_id=disruption_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            severity=request.severity,
            status=DisruptionLifecycleStatus.ACTIVE,
            start_time=start,
            end_time=end,
            source=source,
            description=request.description,
            is_simulated=source.upper() == "SIMULATED",
        )
        for target_type, target_id in targets
    ]


def canonical_disruptions_from_external(
    record: dict[str, Any],
) -> list[CanonicalDisruption]:
    """Convert an external fact record into canonical target events.

    This function deliberately maps only event identity and targets. Numerical
    penalties are applied later by ``DisruptionPolicyConfig`` rather than being
    claimed as facts supplied by PortWatch.
    """

    event_id = str(record.get("event_id") or record.get("disruption_id") or "EXTERNAL")
    event_type = _canonical_event_type(record.get("event_type"))
    start = _parse_datetime(record.get("start_time"), EPOCH)
    end = _parse_datetime(record.get("end_time"), start + timedelta(hours=24))
    severity = str(
        record.get("severity")
        or record.get("severity_text")
        or record.get("alert_level")
        or "MEDIUM"
    ).upper()
    targets = [
        (DisruptionTargetType.LOCATION, str(location_id))
        for location_id in record.get("affected_location_ids", []) or []
    ]
    targets.extend(
        (DisruptionTargetType.ROUTE, str(route_id))
        for route_id in record.get("affected_route_ids", []) or []
    )
    return [
        CanonicalDisruption(
            disruption_id=event_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            severity=severity,
            status=DisruptionLifecycleStatus.ACTIVE,
            start_time=start,
            end_time=end,
            source=str(record.get("source") or "EXTERNAL"),
            description=record.get("description") or record.get("event_name"),
            is_simulated=False,
        )
        for target_type, target_id in targets
    ]
