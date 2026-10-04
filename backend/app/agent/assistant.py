"""Build trusted assistant context from persisted application records."""

from __future__ import annotations

from typing import Any

from ..repository import get_run, load_supply_chain_data
from ..schemas import AssistantRequest


def _request_from_stored_run(stored: dict[str, Any]) -> dict[str, Any]:
    disruption = stored.get("disruption") or {}
    return disruption.get("request", disruption)


def _stored_context(stored: dict[str, Any], shipment_id: str | None) -> dict[str, Any]:
    results = stored.get("results") or {}
    disruption = _request_from_stored_run(stored)
    affected = results.get("affected_shipments") or []
    recommendations = results.get("recommendations") or []

    if not affected and recommendations:
        _, _, shipments = load_supply_chain_data()
        shipment_by_id = {
            shipment.id: {
                "id": shipment.id,
                "destination_id": shipment.destination_id,
                "priority": shipment.priority.value,
            }
            for shipment in shipments
        }
        affected = [
            shipment_by_id[recommendation["shipment_id"]]
            for recommendation in recommendations
            if recommendation.get("shipment_id") in shipment_by_id
        ]

    if shipment_id:
        affected = [shipment for shipment in affected if shipment.get("id") == shipment_id]
        recommendations = [
            recommendation
            for recommendation in recommendations
            if recommendation.get("shipment_id") == shipment_id
        ]

    locations, _, _ = load_supply_chain_data()
    return {
        "disruption": disruption,
        "affected_shipments": affected,
        "recommendations": recommendations,
        "locations": {location.id: location.name for location in locations},
        "source_record_id": stored.get("disruption", {}).get("id"),
    }


def build_assistant_context(request: AssistantRequest) -> dict[str, Any]:
    """Return server-owned context when an assistant record ID is provided.

    ``context`` remains a compatibility path for the current unsaved
    interactive planner. Once a simulation or decision exists, callers should
    send its identifier and the browser context is deliberately ignored.
    """

    record_id = request.simulation_run_id or request.disruption_id
    if not record_id:
        return request.context

    stored = get_run(record_id)
    if stored is None:
        raise LookupError(f"Assistant record {record_id} was not found")
    return _stored_context(stored, request.shipment_id)
