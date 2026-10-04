import json
from openai import APIConnectionError, APITimeoutError, OpenAI
from .config import settings
from .services import validate_explanation


def _offline_explanation(record: dict) -> dict:
    selected = record.get("selected_route")
    original = record.get("original_route")
    status = record.get("status", "ROUTE_FOUND")
    delay_saved = record.get("delay_saved_hours", 0)
    additional_cost = record.get("additional_cost", 0)

    route_unchanged = bool(
        original
        and selected
        and original.get("location_ids") == selected.get("location_ids")
    )

    if route_unchanged:
        summary = "The original route is not affected by the active disruption and remains the recommended route."
        recommended_action = "Continue with the original route."
        reasoning = (
            f"The original route remains available at {original['duration_hours']} hours, "
            f"a cost of {original['cost']}, risk score {original['risk_score']}, "
            f"and capacity feasibility set to {original['capacity_feasible']}."
        )
        risk_warning = "Continue monitoring the route for changes to disruption status or capacity."
    elif selected:
        summary = (
            "Deterministic routing selected the highest-ranked capacity-feasible "
            "alternative route."
        )
        recommended_action = "Review and approve the selected route."
        reasoning = (
            f"The selected route has {selected['duration_hours']} hours of duration, "
            f"a cost of {selected['cost']}, risk score {selected['risk_score']}, "
            f"and capacity feasibility set to {selected['capacity_feasible']}."
        )
        risk_warning = (
            "Review the selected route's risk score and remaining capacity before "
            "operational execution."
        )
    else:
        summary = "Deterministic routing found no feasible alternative route."
        recommended_action = "Review the disruption and capacity constraints."
        reasoning = f"The decision status is {status}; no selected route was returned."
        risk_warning = "Do not dispatch this recommendation without a feasible route."

    if original and selected:
        reasoning += (
            f" The baseline route was {original['duration_hours']} hours and the "
            f"selected route changes the estimated delay by {delay_saved} hours "
            f"with an additional cost of {additional_cost}."
        )

    return {
        "summary": summary,
        "recommended_action": recommended_action,
        "reasoning_summary": reasoning,
        "delay_saved_hours": delay_saved,
        "additional_cost": additional_cost,
        "risk_warning": risk_warning,
        "next_steps": [
            "Confirm the disruption status and route capacity.",
            "Review the deterministic route comparison before execution.",
        ],
        "source": "offline_deterministic",
    }


def explain(record: dict) -> dict:
    if not settings.openai_api_key:
        return _offline_explanation(record)
    schema={"type":"object","additionalProperties":False,"required":["summary","recommended_action","reasoning_summary","delay_saved_hours","additional_cost","risk_warning","next_steps"],"properties":{"summary":{"type":"string"},"recommended_action":{"type":"string"},"reasoning_summary":{"type":"string"},"delay_saved_hours":{"type":"number"},"additional_cost":{"type":"number"},"risk_warning":{"type":"string"},"next_steps":{"type":"array","items":{"type":"string"}}}}
    client=OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    try:
        response=client.responses.create(model=settings.openai_model,input=[{"role":"system","content":"Explain only the supplied decision record. Do not add IDs, routes, locations, or numbers."},{"role":"user","content":json.dumps(record)}],text={"format":{"type":"json_schema","name":"reroute_explanation","strict":True,"schema":schema}})
    except (APIConnectionError, APITimeoutError):
        fallback = _offline_explanation(record)
        fallback["fallback_reason"] = "provider_unavailable"
        return fallback
    result = validate_explanation(json.loads(response.output_text),record)
    result["source"] = "openai"
    return result


def _route_text(route: dict | None, locations: dict) -> str:
    if not route:
        return "No route"
    return " → ".join(locations.get(identifier, identifier) for identifier in route.get("location_ids", []))


def _offline_assistant_answer(question: str, context: dict) -> dict:
    normalized = question.lower()
    locations = context.get("locations", {})
    plan = context.get("plan") or {}
    disruption = context.get("disruption") or {}
    affected = context.get("affected_shipments") or []
    recommendations = context.get("recommendations") or []
    evidence: list[str] = []

    if any(word in normalized for word in ("priority", "highest", "top 5", "top five")) and "shipment" in normalized:
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        ranked = sorted(affected, key=lambda item: (priority_order.get(item.get("priority", "LOW"), 3), item.get("id", "")))[:5]
        if not ranked:
            return {"answer": "No affected shipments are currently displayed. Run a selected disruption first.", "evidence": [], "source": "offline_deterministic"}
        lines = []
        for shipment in ranked:
            destination = locations.get(shipment.get("destination_id"), shipment.get("destination_id", "unknown destination"))
            lines.append(f"{shipment.get('id')} ({shipment.get('priority', 'unknown')} priority) → {destination}")
        evidence = [f"Affected shipment count: {len(affected)}"]
        return {"answer": "Top affected shipments by priority: " + "; ".join(lines) + ".", "evidence": evidence, "source": "offline_deterministic"}

    if "customer" in normalized or "customers" in normalized:
        counts: dict[str, int] = {}
        for shipment in affected:
            destination = shipment.get("destination_id", "unknown")
            counts[destination] = counts.get(destination, 0) + 1
        if not counts:
            return {"answer": "No affected customers are currently displayed. Run a selected disruption first.", "evidence": [], "source": "offline_deterministic"}
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        summary = "; ".join(f"{locations.get(identifier, identifier)} ({count} shipment{'s' if count != 1 else ''})" for identifier, count in ranked)
        evidence = [f"Affected shipments used: {len(affected)}"]
        return {"answer": f"Customers most affected in the current view are: {summary}.", "evidence": evidence, "source": "offline_deterministic"}

    if any(word in normalized for word in ("cost", "time", "eta", "compare", "alternative", "route")) and plan:
        original = plan.get("original_route")
        candidates = plan.get("candidate_routes") or []
        if not candidates:
            answer = "There are no other capacity-feasible routes in the current plan. The original route is unavailable or every alternative is blocked or over capacity."
            if original:
                answer += f" The original route was {_route_text(original, locations)} at {original.get('duration_hours')} hours and cost {original.get('cost')}."
            return {"answer": answer, "evidence": [f"Plan status: {plan.get('status', 'unknown')}"], "source": "offline_deterministic"}
        comparisons = []
        for index, route in enumerate(candidates, start=1):
            comparisons.append(f"Alternative {index}: {_route_text(route, locations)}, {route.get('duration_hours')} hours, cost {route.get('cost')}, risk {route.get('risk_score')}, capacity feasible {route.get('capacity_feasible')}")
        answer = "Current route comparison: " + "; ".join(comparisons) + "."
        if original:
            answer += f" Baseline: {_route_text(original, locations)}, {original.get('duration_hours')} hours, cost {original.get('cost')}, risk {original.get('risk_score')}."
        evidence = [f"Candidate routes returned: {len(candidates)}"]
        return {"answer": answer, "evidence": evidence, "source": "offline_deterministic"}

    if any(word in normalized for word in ("why", "disrupt", "interrupt", "blocked", "reason")):
        if not disruption:
            return {"answer": "No disruption has been run in the current dashboard state.", "evidence": [], "source": "offline_deterministic"}
        affected_locations = ", ".join(locations.get(identifier, identifier) for identifier in disruption.get("affected_location_ids", [])) or "no locations"
        affected_routes = ", ".join(disruption.get("affected_route_ids", [])) or "no route IDs"
        answer = f"The current disruption is {disruption.get('disruption_type', 'UNKNOWN')} with {disruption.get('severity', 'unknown')} severity for {disruption.get('duration_hours', 'unknown')} hours. Affected locations: {affected_locations}. Affected routes: {affected_routes}."
        evidence = [f"Affected shipment count: {len(affected)}"]
        return {"answer": answer, "evidence": evidence, "source": "offline_deterministic"}

    if plan:
        selected = plan.get("selected_route")
        answer = f"The current plan status is {plan.get('status', 'unknown')} with {len(plan.get('candidate_routes') or [])} candidate route(s)."
        if selected:
            answer += f" The selected route is {_route_text(selected, locations)} and takes {selected.get('duration_hours')} hours at cost {selected.get('cost')}."
        evidence = [f"Affected shipments displayed: {len(affected)}", f"Reroute recommendations displayed: {len(recommendations)}"]
        return {"answer": answer, "evidence": evidence, "source": "offline_deterministic"}

    return {"answer": "I can answer questions about the currently displayed route plan, disruption reason, route cost/time/risk, affected shipments, priorities, and customers. Run a route or disruption so there is current data to inspect.", "evidence": [], "source": "offline_deterministic"}


def answer_question(question: str, context: dict) -> dict:
    fallback = _offline_assistant_answer(question, context)
    if not settings.openai_api_key:
        return fallback

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer", "evidence"],
        "properties": {
            "answer": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
    }
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": "Answer only from the supplied dashboard context. Do not invent facts, identifiers, routes, locations, costs, times, risks, or shipment counts. Do not select or alter routes. If the context does not contain the answer, say so."},
                {"role": "user", "content": json.dumps({"question": question, "dashboard_context": context})},
            ],
            text={"format": {"type": "json_schema", "name": "dashboard_answer", "strict": True, "schema": schema}},
        )
    except (APIConnectionError, APITimeoutError):
        fallback["fallback_reason"] = "provider_unavailable"
        return fallback
    result = json.loads(response.output_text)
    result["source"] = "openai"
    return result
