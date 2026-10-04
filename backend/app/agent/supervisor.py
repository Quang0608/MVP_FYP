"""One bounded Supervisor Agent over deterministic trusted tools."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Type

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI
from pydantic import BaseModel, ValidationError

from ..config import settings
from ..schemas import ImpactClassification, Priority
from .schemas import (
    AffectedShipmentsInput,
    AffectedShipmentsOutput,
    CandidateRoutesInput,
    EmptyInput,
    IncidentState,
    LocationQueryInput,
    ShipmentFilterInput,
    ShipmentInput,
    ShipmentSimulationInput,
    SimulateDisruptionInput,
    SimulateDisruptionOutput,
    SimulationInput,
    SupervisorRequest,
    SupervisorResponse,
    ToolError,
    ToolInvocation,
    ValidateRouteCandidateInput,
)
from .tools import (
    AgentToolError,
    get_active_disruptions,
    get_affected_shipments,
    get_disruption,
    get_route_comparison,
    get_scenario_network_summary,
    get_shipment,
    get_shipment_impact,
    get_shipment_route,
    get_shipments,
    generate_candidate_routes,
    get_simulation,
    resolve_location,
    simulate_disruption,
    validate_route_candidate,
)


MAX_TOOL_ITERATIONS = 4


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: Type[BaseModel]
    handler: Callable[[BaseModel], BaseModel | list[BaseModel]]

    def openai_definition(self) -> dict[str, object]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }


def _shipment(input_model: ShipmentInput):
    return get_shipment(input_model.shipment_id)


def _shipment_route(input_model: ShipmentInput):
    return get_shipment_route(input_model.shipment_id)


def _active_disruptions(input_model: EmptyInput):
    return get_active_disruptions()


def _location(input_model: LocationQueryInput):
    return resolve_location(input_model.name_or_id)


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_shipment",
        "Read one trusted shipment summary by runtime shipment ID.",
        ShipmentInput,
        _shipment,
    ),
    ToolSpec(
        "get_shipment_route",
        "Read the ordered route legs and progress state for one shipment.",
        ShipmentInput,
        _shipment_route,
    ),
    ToolSpec(
        "get_shipments",
        "Read a bounded list of trusted shipments using simple filters.",
        ShipmentFilterInput,
        get_shipments,
    ),
    ToolSpec(
        "get_active_disruptions",
        "Read currently active simulated disruptions from persisted runtime state.",
        EmptyInput,
        _active_disruptions,
    ),
    ToolSpec(
        "get_disruption",
        "Read one persisted simulation summary by simulation run ID.",
        SimulationInput,
        get_disruption,
    ),
    ToolSpec(
        "resolve_location",
        "Resolve an operator location name or ID to canonical runtime identity; return ambiguity instead of guessing.",
        LocationQueryInput,
        _location,
    ),
    ToolSpec(
        "get_simulation",
        "Read a compact trusted network and impact summary for a simulation.",
        SimulationInput,
        get_simulation,
    ),
    ToolSpec(
        "get_scenario_network_summary",
        "Read available and unavailable route counts for a persisted scenario.",
        SimulationInput,
        get_scenario_network_summary,
    ),
    ToolSpec(
        "get_affected_shipments",
        "Run deterministic impact detection and return affected shipment evidence.",
        AffectedShipmentsInput,
        get_affected_shipments,
    ),
    ToolSpec(
        "get_shipment_impact",
        "Run deterministic impact detection for one shipment in a simulation.",
        ShipmentSimulationInput,
        get_shipment_impact,
    ),
    ToolSpec(
        "get_route_comparison",
        "Compare the deterministic baseline and capacity-feasible candidate routes for a shipment.",
        ShipmentSimulationInput,
        get_route_comparison,
    ),
    ToolSpec(
        "generate_candidate_routes",
        "Generate deterministic candidate routes for a shipment in a scenario.",
        CandidateRoutesInput,
        generate_candidate_routes,
    ),
    ToolSpec(
        "validate_route_candidate",
        "Validate an ordered route candidate against the deterministic scenario graph.",
        ValidateRouteCandidateInput,
        validate_route_candidate,
    ),
    ToolSpec(
        "simulate_disruption",
        "Create one validated simulated disruption through the same service as the dashboard.",
        SimulateDisruptionInput,
        simulate_disruption,
    ),
)


class ToolRegistry:
    def __init__(self, specs: tuple[ToolSpec, ...] = TOOL_SPECS) -> None:
        self._specs = {spec.name: spec for spec in specs}

    @property
    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def invoke(self, name: str, arguments: dict[str, object]) -> BaseModel | list[BaseModel]:
        spec = self._specs.get(name)
        if spec is None:
            raise AgentToolError("UNKNOWN_TOOL", f"Tool {name} is not available.")
        try:
            validated = spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError(
                "INVALID_TOOL_INPUT",
                f"Invalid input for {name}.",
                {"errors": exc.errors()},
            ) from exc
        return spec.handler(validated)


def _as_json(value: BaseModel | list[BaseModel]) -> object:
    if isinstance(value, list):
        return [item.model_dump(mode="json") for item in value]
    return value.model_dump(mode="json")


def _tool_record(
    name: str,
    arguments: dict[str, object],
    *,
    error: AgentToolError | None = None,
) -> ToolInvocation:
    return ToolInvocation(
        tool_name=name,
        input=arguments,
        success=error is None,
        error=(
            ToolError(code=error.code, message=error.message, details=error.details)
            if error
            else None
        ),
    )


def _extract_shipment_id(question: str) -> str | None:
    match = re.search(r"\b(?:ASIA_S|SHP|S)[-_][A-Za-z0-9_-]+\b", question, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_duration(question: str) -> int | None:
    match = re.search(r"\b(\d+)\s*hours?\b", question, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _simulation_id(request: SupervisorRequest, question: str) -> str | None:
    if request.simulation_run_id or request.disruption_id:
        return request.simulation_run_id or request.disruption_id
    match = re.search(r"\bSIM-[A-Za-z0-9_-]+\b", question, re.IGNORECASE)
    return match.group(0) if match else None


class SupervisorAgent:
    """Bounded tool-using supervisor; it never computes operational results."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.max_tool_iterations = max(1, min(max_tool_iterations, MAX_TOOL_ITERATIONS))

    def run(self, request: SupervisorRequest) -> SupervisorResponse:
        if settings.openai_api_key:
            try:
                return self._run_provider(request)
            except (APIConnectionError, APITimeoutError, APIError):
                fallback = self._run_offline(request)
                fallback.fallback_reason = "provider_unavailable"
                return fallback
        return self._run_offline(request)

    def _run_offline(self, request: SupervisorRequest) -> SupervisorResponse:
        question = request.question
        normalized = question.lower()
        state = IncidentState(user_request=question)
        calls: list[ToolInvocation] = []
        evidence: list[str] = []

        def call(name: str, arguments: dict[str, object]):
            try:
                result = self.registry.invoke(name, arguments)
                calls.append(_tool_record(name, arguments))
                return result
            except AgentToolError as exc:
                calls.append(_tool_record(name, arguments, error=exc))
                raise

        try:
            if any(word in normalized for word in ("simulate", "close", "shutdown")):
                return self._offline_simulation(request, state, calls, evidence, call)

            simulation_id = _simulation_id(request, question)
            shipment_id = request.shipment_id or _extract_shipment_id(question)

            if any(word in normalized for word in ("active disruption", "current disruption", "what disruptions")):
                result = call("get_active_disruptions", {})
                answer = self._active_disruption_answer(result, evidence)
                return self._response(answer, evidence, calls, state)

            if "compare" in normalized and shipment_id and simulation_id:
                call("get_shipment", {"shipment_id": shipment_id})
                result = call(
                    "get_route_comparison",
                    {"shipment_id": shipment_id, "simulation_run_id": simulation_id},
                )
                answer = self._route_comparison_answer(result, evidence)
                return self._response(answer, evidence, calls, state)

            if any(word in normalized for word in ("why", "reason", "reroute required", "marked")) and shipment_id and simulation_id:
                call("get_shipment", {"shipment_id": shipment_id})
                result = call(
                    "get_shipment_impact",
                    {"shipment_id": shipment_id, "simulation_run_id": simulation_id},
                )
                answer = self._impact_answer(result, evidence)
                state.simulation_run_id = simulation_id
                state.affected_shipments = [result]
                return self._response(answer, evidence, calls, state)

            if any(word in normalized for word in ("affected", "at risk", "impacted")) and simulation_id:
                call("get_simulation", {"simulation_run_id": simulation_id})
                priority = Priority.HIGH if "high-priority" in normalized or "high priority" in normalized else None
                arguments: dict[str, object] = {"simulation_run_id": simulation_id, "limit": 50}
                if priority:
                    arguments["priority"] = priority.value
                result = call("get_affected_shipments", arguments)
                state.simulation_run_id = simulation_id
                state.affected_shipments = result.shipments
                state.prioritized_shipments = [item.shipment.shipment_id for item in result.shipments]
                answer = self._affected_answer(result, priority, evidence)
                return self._response(answer, evidence, calls, state)

            return self._response(
                "I need a shipment ID and simulation ID for shipment analysis, or a specific operational question such as active disruptions or a route comparison.",
                evidence,
                calls,
                state,
            )
        except AgentToolError as exc:
            return self._response(
                f"I could not complete that request: {exc.message}",
                evidence,
                calls,
                state,
            )

    def _offline_simulation(self, request, state, calls, evidence, call):
        duration = _extract_duration(request.question)
        if duration is None:
            return self._response(
                "Please provide a disruption duration in hours before I run the simulation.",
                evidence,
                calls,
                state,
            )
        question_without_duration = re.sub(
            r"\bfor\s+\d+\s*hours?\b",
            "",
            request.question,
            flags=re.IGNORECASE,
        ).strip(" .,")
        target_match = re.search(
            r"(?:close|closing|shutdown|shutting down)(?:\s+of|\s+at)?\s+(.+)$",
            question_without_duration,
            re.IGNORECASE,
        )
        if target_match is None:
            target_match = re.search(
                r"(.+?)\s+(?:close|closing|shutdown|shutting down)$",
                question_without_duration,
                re.IGNORECASE,
            )
        target = target_match.group(1).strip(" .,") if target_match else request.question
        target = re.sub(r"^simulate\s+", "", target, flags=re.IGNORECASE).strip(" .,")
        resolved = call("resolve_location", {"name_or_id": target})
        if resolved.ambiguous or resolved.resolved is None:
            return self._response(
                "The location could not be resolved to one trusted runtime entity. Please provide a more specific name or ID.",
                evidence,
                calls,
                state,
            )
        state.resolved_entities = [resolved.resolved]
        simulation_input = {
            "disruption_type": "PORT_CLOSURE",
            "target_id": resolved.resolved.location_id,
            "duration_hours": duration,
            "severity": "HIGH",
        }
        state.canonical_disruption = SimulateDisruptionInput.model_validate(simulation_input)
        simulation = call("simulate_disruption", simulation_input)
        state.incident_id = simulation.simulation_run_id
        state.simulation_run_id = simulation.simulation_run_id
        affected = call(
            "get_affected_shipments",
            {"simulation_run_id": simulation.simulation_run_id, "limit": 50},
        )
        state.affected_shipments = affected.shipments
        state.prioritized_shipments = [item.shipment.shipment_id for item in affected.shipments]
        evidence.append(f"Simulation ID: {simulation.simulation_run_id}")
        evidence.append(f"Affected shipments: {affected.total}")
        return self._response(
            f"The {resolved.resolved.name} port closure simulation ran for {duration} hours. It created simulation {simulation.simulation_run_id} and identified {affected.total} affected shipment(s).",
            evidence,
            calls,
            state,
        )

    def _run_provider(self, request: SupervisorRequest) -> SupervisorResponse:
        client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        system = (
            "You are a bounded supply-chain Supervisor. Use trusted tools for every operational fact. "
            "Never calculate routes, impact, capacity, risk, or costs yourself. Never invent IDs. "
            "Use simulate_disruption only for an explicit user simulation request and then inspect its result. "
            "Return a concise answer grounded in tool outputs."
        )
        inputs: list[object] = [
            {"role": "system", "content": system},
            {"role": "user", "content": request.question},
        ]
        calls: list[ToolInvocation] = []
        state = IncidentState(user_request=request.question)
        evidence: list[str] = []
        for _ in range(self.max_tool_iterations):
            response = client.responses.create(
                model=settings.openai_model,
                input=inputs,
                tools=[spec.openai_definition() for spec in self.registry.specs],
            )
            output_items = list(getattr(response, "output", []) or [])
            function_calls = [item for item in output_items if _item_value(item, "type") == "function_call"]
            if not function_calls:
                answer = getattr(response, "output_text", "") or "The Supervisor returned no grounded answer."
                return self._response(answer, evidence, calls, state, source="openai_supervisor")
            inputs.extend(output_items)
            for function_call in function_calls:
                name = str(_item_value(function_call, "name"))
                raw_arguments = _item_value(function_call, "arguments") or "{}"
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                try:
                    result = self.registry.invoke(name, arguments)
                    calls.append(_tool_record(name, arguments))
                    evidence.append(f"{name} returned trusted structured data.")
                    self._update_state_from_tool(state, result)
                    tool_output = {"ok": True, "result": _as_json(result)}
                except (AgentToolError, json.JSONDecodeError) as exc:
                    if isinstance(exc, AgentToolError):
                        calls.append(_tool_record(name, arguments, error=exc))
                        tool_output = {"ok": False, "error": exc.message, "code": exc.code}
                    else:
                        tool_output = {"ok": False, "error": "Tool arguments were not valid JSON."}
                inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": _item_value(function_call, "call_id"),
                        "output": json.dumps(tool_output),
                    }
                )
        return self._response(
            "The Supervisor stopped after reaching its tool-call limit. No further operational action was taken.",
            evidence,
            calls,
            state,
            source="supervisor_limit",
        )

    @staticmethod
    def _response(answer, evidence, calls, state, source="offline_supervisor"):
        return SupervisorResponse(
            answer=answer,
            evidence=evidence,
            source=source,
            tool_calls=calls,
            state=state,
        )

    @staticmethod
    def _update_state_from_tool(state, result) -> None:
        if isinstance(result, SimulateDisruptionOutput):
            state.incident_id = result.simulation_run_id
            state.simulation_run_id = result.simulation_run_id
        elif isinstance(result, AffectedShipmentsOutput):
            state.simulation_run_id = result.simulation_run_id
            state.affected_shipments = result.shipments
            state.prioritized_shipments = [
                item.shipment.shipment_id for item in result.shipments
            ]

    @staticmethod
    def _active_disruption_answer(result, evidence):
        if not result:
            return "There are no active simulated disruptions in the trusted runtime state."
        evidence.append(f"Active disruption targets: {len(result)}")
        return "Active disruptions: " + "; ".join(
            f"{item.disruption_type} at {item.target_id} ({item.severity}, {item.duration_hours} hours)"
            for item in result
        ) + "."

    @staticmethod
    def _affected_answer(result, priority, evidence):
        label = "high-priority " if priority == Priority.HIGH else ""
        evidence.append(f"Affected shipment records returned: {result.total}")
        if not result.shipments:
            return f"No affected {label}shipments were found in the simulation."
        preview = ", ".join(item.shipment.shipment_id for item in result.shipments[:10])
        return f"The simulation has {result.total} affected {label}shipment(s). The returned shipment IDs include: {preview}."

    @staticmethod
    def _impact_answer(result, evidence):
        evidence.append(f"Impact classification: {result.classification.value}")
        return (
            f"{result.shipment.shipment_id} is classified as {result.classification.value}. "
            f"Reason: {result.reason}. Route feasible: {result.route_feasible}."
        )

    @staticmethod
    def _route_comparison_answer(result, evidence):
        evidence.append(f"Candidate routes returned: {len(result.candidate_routes)}")
        if not result.candidate_routes:
            return f"No feasible candidate route was found for {result.shipment_id} in the simulation."
        selected = result.selected_route
        return (
            f"The deterministic comparison returned {len(result.candidate_routes)} candidate route(s) for {result.shipment_id}. "
            f"The highest-ranked candidate takes {selected.duration_hours} hours, costs {selected.cost}, "
            f"has risk {selected.risk_score}, and is SLA-feasible: {selected.sla_met}."
        )


def _item_value(item: object, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def run_supervisor(request: SupervisorRequest) -> SupervisorResponse:
    return SupervisorAgent().run(request)
