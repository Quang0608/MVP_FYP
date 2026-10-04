"""Deterministic Asia operational-network and shipment population generator.

The generator deliberately combines real, geometry-bearing canonical WPI ports
with synthetic enterprise entities and derived logistics connections. It is a
dataset builder, not a routing or disruption-policy implementation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from random import Random
from typing import Iterable

import networkx as nx

from .domain import (
    Location,
    LocationType,
    Priority,
    Route,
    RuntimeDataset,
    Shipment,
    ShipmentRouteLeg,
    Status,
)
from .graph import build_supply_chain_graph
from .external_state.corridors import corridor_memberships_for_route
from .external_state.geospatial import interpolate_weather_sample_points
from .integrations.canonical import load_port_master_locations
from .services import find_candidate_routes


@dataclass(frozen=True)
class AsiaGenerationConfig:
    seed: int = 20260913
    shipment_count: int = 220
    factory_count: int = 12
    warehouse_count: int = 14
    customer_count: int = 14
    region: str = "Asia"


@dataclass(frozen=True)
class AsiaDatasetReport:
    real_ports: int
    synthetic_factories: int
    synthetic_warehouses: int
    synthetic_customers: int
    routes: int
    shipments: int
    status_distribution: dict[str, int]
    priority_distribution: dict[str, int]
    countries: tuple[str, ...]
    connected_components: int
    shipments_with_alternatives: int


ASIA_PORT_IDS = (
    # Singapore and Malaysia
    "LOC_WPI_50000",
    "LOC_WPI_50017",
    "LOC_WPI_57410",
    "LOC_WPI_49930",
    "LOC_WPI_51587",
    "LOC_WPI_51585",
    # Vietnam and Thailand
    "LOC_WPI_57570",
    "LOC_WPI_57580",
    "LOC_WPI_57680",
    "LOC_WPI_57650",
    "LOC_WPI_57439",
    "LOC_WPI_57450",
    "LOC_WPI_57462",
    "LOC_WPI_57437",
    # Indonesia and the Philippines
    "LOC_WPI_51130",
    "LOC_WPI_50970",
    "LOC_WPI_50730",
    "LOC_WPI_51040",
    "LOC_WPI_58370",
    "LOC_WPI_59430",
    "LOC_WPI_58395",
    "LOC_WPI_58960",
    "LOC_WPI_58320",
    # China and Hong Kong
    "LOC_WPI_60250",
    "LOC_WPI_57830",
    "LOC_WPI_60140",
    "LOC_WPI_59940",
    "LOC_WPI_59970",
    "LOC_WPI_60190",
    "LOC_WPI_57857",
    "LOC_WPI_57870",
    "LOC_WPI_57840",
    # Japan and South Korea
    "LOC_WPI_61560",
    "LOC_WPI_61375",
    "LOC_WPI_61385",
    "LOC_WPI_62430",
    "LOC_WPI_61480",
    "LOC_WPI_61380",
    "LOC_WPI_61390",
    "LOC_WPI_61550",
    "LOC_WPI_60325",
    "LOC_WPI_60376",
    "LOC_WPI_60400",
    "LOC_WPI_60390",
    # India and Sri Lanka
    "LOC_WPI_48617",
    "LOC_WPI_49130",
    "LOC_WPI_48845",
    "LOC_WPI_49450",
    "LOC_WPI_48840",
    "LOC_WPI_48630",
    "LOC_WPI_49240",
)


FACTORY_ANCHORS = (
    ("LOC_WPI_50000", "LOC_WPI_51587"),
    ("LOC_WPI_49930", "LOC_WPI_50000"),
    ("LOC_WPI_57580", "LOC_WPI_57462"),
    ("LOC_WPI_57680", "LOC_WPI_59970"),
    ("LOC_WPI_57462", "LOC_WPI_49930"),
    ("LOC_WPI_50970", "LOC_WPI_51130"),
    ("LOC_WPI_51130", "LOC_WPI_50970"),
    ("LOC_WPI_58370", "LOC_WPI_57840"),
    ("LOC_WPI_59970", "LOC_WPI_59940"),
    ("LOC_WPI_60390", "LOC_WPI_59970"),
    ("LOC_WPI_48840", "LOC_WPI_48617"),
    ("LOC_WPI_49450", "LOC_WPI_49240"),
)


WAREHOUSE_ANCHORS = (
    ("LOC_WPI_50000", "LOC_WPI_49930"),
    ("LOC_WPI_49930", "LOC_WPI_51587"),
    ("LOC_WPI_57580", "LOC_WPI_50000"),
    ("LOC_WPI_57462", "LOC_WPI_49930"),
    ("LOC_WPI_50970", "LOC_WPI_51130"),
    ("LOC_WPI_58370", "LOC_WPI_57840"),
    ("LOC_WPI_59970", "LOC_WPI_59940"),
    ("LOC_WPI_60140", "LOC_WPI_60390"),
    ("LOC_WPI_61380", "LOC_WPI_61390"),
    ("LOC_WPI_49450", "LOC_WPI_48840"),
    ("LOC_WPI_48617", "LOC_WPI_49240"),
    ("LOC_WPI_60390", "LOC_WPI_59970"),
    ("LOC_WPI_50970", "LOC_WPI_49930"),
    ("LOC_WPI_50000", "LOC_WPI_49450"),
)


PORT_CORRIDORS = (
    ("LOC_WPI_50000", "LOC_WPI_49930"),
    ("LOC_WPI_50000", "LOC_WPI_51587"),
    ("LOC_WPI_50000", "LOC_WPI_50970"),
    ("LOC_WPI_49930", "LOC_WPI_50000"),
    ("LOC_WPI_49930", "LOC_WPI_51587"),
    ("LOC_WPI_49930", "LOC_WPI_48840"),
    ("LOC_WPI_51587", "LOC_WPI_50000"),
    ("LOC_WPI_51587", "LOC_WPI_57580"),
    ("LOC_WPI_57580", "LOC_WPI_50000"),
    ("LOC_WPI_57580", "LOC_WPI_57462"),
    ("LOC_WPI_57580", "LOC_WPI_58370"),
    ("LOC_WPI_57680", "LOC_WPI_59970"),
    ("LOC_WPI_57680", "LOC_WPI_57840"),
    ("LOC_WPI_57680", "LOC_WPI_58370"),
    ("LOC_WPI_57462", "LOC_WPI_50000"),
    ("LOC_WPI_57462", "LOC_WPI_57580"),
    ("LOC_WPI_57462", "LOC_WPI_49930"),
    ("LOC_WPI_50970", "LOC_WPI_50000"),
    ("LOC_WPI_50970", "LOC_WPI_51130"),
    ("LOC_WPI_50970", "LOC_WPI_49240"),
    ("LOC_WPI_51130", "LOC_WPI_50970"),
    ("LOC_WPI_51130", "LOC_WPI_50000"),
    ("LOC_WPI_58370", "LOC_WPI_57840"),
    ("LOC_WPI_58370", "LOC_WPI_59970"),
    ("LOC_WPI_58370", "LOC_WPI_50000"),
    ("LOC_WPI_59430", "LOC_WPI_58370"),
    ("LOC_WPI_58395", "LOC_WPI_57840"),
    ("LOC_WPI_58960", "LOC_WPI_58370"),
    ("LOC_WPI_57840", "LOC_WPI_57857"),
    ("LOC_WPI_57840", "LOC_WPI_59970"),
    ("LOC_WPI_57857", "LOC_WPI_57840"),
    ("LOC_WPI_57857", "LOC_WPI_59970"),
    ("LOC_WPI_57870", "LOC_WPI_59970"),
    ("LOC_WPI_59970", "LOC_WPI_59940"),
    ("LOC_WPI_59970", "LOC_WPI_60390"),
    ("LOC_WPI_59970", "LOC_WPI_61380"),
    ("LOC_WPI_59970", "LOC_WPI_57840"),
    ("LOC_WPI_59940", "LOC_WPI_59970"),
    ("LOC_WPI_59940", "LOC_WPI_60390"),
    ("LOC_WPI_59940", "LOC_WPI_61550"),
    ("LOC_WPI_60140", "LOC_WPI_60390"),
    ("LOC_WPI_60140", "LOC_WPI_59970"),
    ("LOC_WPI_60140", "LOC_WPI_61380"),
    ("LOC_WPI_61380", "LOC_WPI_61390"),
    ("LOC_WPI_61380", "LOC_WPI_61550"),
    ("LOC_WPI_61380", "LOC_WPI_60390"),
    ("LOC_WPI_61390", "LOC_WPI_61380"),
    ("LOC_WPI_61390", "LOC_WPI_60390"),
    ("LOC_WPI_61550", "LOC_WPI_60390"),
    ("LOC_WPI_61550", "LOC_WPI_61380"),
    ("LOC_WPI_60390", "LOC_WPI_59970"),
    ("LOC_WPI_60390", "LOC_WPI_60140"),
    ("LOC_WPI_60390", "LOC_WPI_61380"),
    ("LOC_WPI_60390", "LOC_WPI_50000"),
    ("LOC_WPI_48840", "LOC_WPI_48617"),
    ("LOC_WPI_48840", "LOC_WPI_49450"),
    ("LOC_WPI_48840", "LOC_WPI_49240"),
    ("LOC_WPI_48617", "LOC_WPI_48840"),
    ("LOC_WPI_48617", "LOC_WPI_49240"),
    ("LOC_WPI_48617", "LOC_WPI_50000"),
    ("LOC_WPI_49450", "LOC_WPI_48840"),
    ("LOC_WPI_49450", "LOC_WPI_49240"),
    ("LOC_WPI_49450", "LOC_WPI_50000"),
    ("LOC_WPI_49240", "LOC_WPI_48840"),
    ("LOC_WPI_49240", "LOC_WPI_49450"),
    ("LOC_WPI_49240", "LOC_WPI_50970"),
)


SUPPLEMENTAL_PORT_CORRIDORS = (
    ("LOC_WPI_50017", "LOC_WPI_50000"),
    ("LOC_WPI_57410", "LOC_WPI_49930"),
    ("LOC_WPI_51585", "LOC_WPI_51587"),
    ("LOC_WPI_57570", "LOC_WPI_57580"),
    ("LOC_WPI_57650", "LOC_WPI_57580"),
    ("LOC_WPI_57439", "LOC_WPI_57462"),
    ("LOC_WPI_57450", "LOC_WPI_57462"),
    ("LOC_WPI_57437", "LOC_WPI_57462"),
    ("LOC_WPI_50730", "LOC_WPI_50970"),
    ("LOC_WPI_51040", "LOC_WPI_50970"),
    ("LOC_WPI_58320", "LOC_WPI_58370"),
    ("LOC_WPI_60250", "LOC_WPI_60390"),
    ("LOC_WPI_57830", "LOC_WPI_59970"),
    ("LOC_WPI_60190", "LOC_WPI_60140"),
    ("LOC_WPI_61560", "LOC_WPI_61550"),
    ("LOC_WPI_61375", "LOC_WPI_61380"),
    ("LOC_WPI_61385", "LOC_WPI_61380"),
    ("LOC_WPI_62430", "LOC_WPI_61550"),
    ("LOC_WPI_61480", "LOC_WPI_61550"),
    ("LOC_WPI_60325", "LOC_WPI_60390"),
    ("LOC_WPI_60376", "LOC_WPI_60390"),
    ("LOC_WPI_60400", "LOC_WPI_60390"),
    ("LOC_WPI_49130", "LOC_WPI_49450"),
    ("LOC_WPI_48845", "LOC_WPI_48840"),
    ("LOC_WPI_48630", "LOC_WPI_48617"),
    ("LOC_WPI_61550", "LOC_WPI_61380"),
)


def generate_asia_runtime_dataset(
    config: AsiaGenerationConfig | None = None,
) -> RuntimeDataset:
    config = config or AsiaGenerationConfig()
    if config.region != "Asia":
        raise ValueError("Only the Asia operational subset is supported")
    if not 150 <= config.shipment_count <= 300:
        raise ValueError("shipment_count must be between 150 and 300")

    rng = Random(config.seed)
    ports = _select_ports()
    locations = ports + _synthetic_locations(ports, config)
    location_by_id = {location.location_id: location for location in locations}
    routes = _build_routes(location_by_id, rng)
    shipments = _build_shipments(
        locations,
        routes,
        config,
        rng,
    )
    dataset = RuntimeDataset(locations=locations, routes=routes, shipments=shipments)
    validate_asia_dataset(dataset)
    return dataset


def _select_ports() -> list[Location]:
    available = {
        location.location_id: location
        for location in load_port_master_locations()
    }
    missing = sorted(set(ASIA_PORT_IDS) - set(available))
    if missing:
        raise ValueError(f"Asia canonical port IDs are missing from port master: {missing}")
    selected = [available[location_id] for location_id in ASIA_PORT_IDS]
    if len({location.location_id for location in selected}) != len(selected):
        raise ValueError("Asia port subset contains duplicate canonical IDs")
    return selected


def _synthetic_locations(
    ports: list[Location],
    config: AsiaGenerationConfig,
) -> list[Location]:
    port_by_id = {location.location_id: location for location in ports}
    locations: list[Location] = []
    for index, (primary_id, _) in enumerate(FACTORY_ANCHORS[: config.factory_count], 1):
        anchor = port_by_id[primary_id]
        locations.append(
            _nearby_location(
                f"ASIA_F_{index:03}",
                f"Asia Manufacturing Site {index:02}",
                LocationType.FACTORY,
                anchor,
                index,
            )
        )
    for index, (primary_id, _) in enumerate(WAREHOUSE_ANCHORS[: config.warehouse_count], 1):
        anchor = port_by_id[primary_id]
        locations.append(
            _nearby_location(
                f"ASIA_W_{index:03}",
                f"Asia Distribution Centre {index:02}",
                LocationType.WAREHOUSE,
                anchor,
                index + 20,
            )
        )
    warehouse_locations = [
        location for location in locations if location.location_type == LocationType.WAREHOUSE
    ]
    for index in range(1, config.customer_count + 1):
        warehouse = warehouse_locations[(index - 1) % len(warehouse_locations)]
        locations.append(
            _nearby_location(
                f"ASIA_C_{index:03}",
                f"Asia Customer Market {index:02}",
                LocationType.CUSTOMER,
                warehouse,
                index + 40,
            )
        )
    return locations


def _nearby_location(
    location_id: str,
    name: str,
    location_type: LocationType,
    anchor: Location,
    offset_index: int,
) -> Location:
    latitude_offset = ((offset_index % 5) - 2) * 0.08
    longitude_offset = (((offset_index * 3) % 5) - 2) * 0.09
    return Location(
        location_id=location_id,
        name=name,
        location_type=location_type,
        country=anchor.country,
        latitude=max(-90, min(90, anchor.latitude + latitude_offset)),
        longitude=max(-180, min(180, anchor.longitude + longitude_offset)),
        status=Status.ACTIVE,
        source="SYNTHETIC",
        source_entity_id=location_id,
        capacity=500,
    )


def _build_routes(location_by_id: dict[str, Location], rng: Random) -> list[Route]:
    route_pairs: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(source_id: str, destination_id: str, mode: str) -> None:
        if (source_id, destination_id) not in seen:
            seen.add((source_id, destination_id))
            route_pairs.append((source_id, destination_id, mode))

    for index, (primary_id, alternate_id) in enumerate(FACTORY_ANCHORS, 1):
        add_pair(f"ASIA_F_{index:03}", primary_id, "ROAD")
        add_pair(f"ASIA_F_{index:03}", alternate_id, "ROAD")
    for source_id, destination_id in _selected_port_corridors():
        add_pair(source_id, destination_id, "SEA")
    for index, (primary_id, alternate_id) in enumerate(WAREHOUSE_ANCHORS, 1):
        add_pair(primary_id, f"ASIA_W_{index:03}", "ROAD")
        add_pair(alternate_id, f"ASIA_W_{index:03}", "ROAD")
    for index in range(1, 15):
        first_warehouse = ((index - 1) % 14) + 1
        second_warehouse = (index % 14) + 1
        add_pair(f"ASIA_W_{first_warehouse:03}", f"ASIA_C_{index:03}", "ROAD")
        add_pair(f"ASIA_W_{second_warehouse:03}", f"ASIA_C_{index:03}", "ROAD")

    routes = []
    for index, (source_id, destination_id, mode) in enumerate(route_pairs, 1):
        source = location_by_id[source_id]
        destination = location_by_id[destination_id]
        distance = _distance_km(source, destination)
        base_duration = _duration_hours(distance, mode)
        capacity = rng.randint(180, 320) if mode == "SEA" else rng.randint(80, 180)
        base_cost = round(
            distance * (0.82 if mode == "SEA" else 1.8)
            + (480 if mode == "SEA" else 120),
            2,
        )
        risk = min(
            0.95,
            round(
                (0.16 if mode == "SEA" else 0.10)
                + abs(source.latitude - destination.latitude) / 180
                + rng.uniform(0.01, 0.08),
                3,
            ),
        )
        routes.append(
            Route(
                route_id=f"ASIA_R_{index:04}",
                source_location_id=source_id,
                destination_location_id=destination_id,
                transport_mode=mode,
                distance_km=round(distance, 2),
                base_duration_hours=base_duration,
                base_cost=base_cost,
                max_capacity=capacity,
                risk_score=risk,
                current_load=rng.randint(8, min(35, capacity // 4)),
                source="DERIVED_ASIA_SYNTHETIC",
                source_entity_id=f"ASIA_R_{index:04}",
                corridor_ids=corridor_memberships_for_route(
                    source_id,
                    destination_id,
                    mode,
                ),
                weather_sample_points=(
                    interpolate_weather_sample_points(source, destination)
                    if mode == "SEA"
                    else []
                ),
            )
        )
    if not 80 <= len(routes) <= 150:
        raise ValueError(f"Asia route topology generated {len(routes)} routes")
    return routes


def _selected_port_corridors() -> tuple[tuple[str, str], ...]:
    """Keep the directed port layer sparse while connecting every selected port."""

    core = PORT_CORRIDORS[:29] + PORT_CORRIDORS[32:33] + PORT_CORRIDORS[34:36]
    return tuple(SUPPLEMENTAL_PORT_CORRIDORS) + core + PORT_CORRIDORS[54:]


def _build_shipments(
    locations: list[Location],
    routes: list[Route],
    config: AsiaGenerationConfig,
    rng: Random,
) -> list[Shipment]:
    factories = [location for location in locations if location.location_type == LocationType.FACTORY]
    customers = [location for location in locations if location.location_type == LocationType.CUSTOMER]
    graph = build_supply_chain_graph(locations, routes)
    pair_order = [(factory, customer) for factory in factories for customer in customers]
    rng.shuffle(pair_order)
    if not pair_order:
        raise ValueError("Asia dataset has no factory/customer shipment pairs")

    shipments: list[Shipment] = []
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cargo_types = ("ELECTRONICS", "APPAREL", "MACHINERY", "CONSUMER_GOODS", "COMPONENTS")
    for index in range(config.shipment_count):
        pair_found = False
        for attempt in range(len(pair_order)):
            factory, customer = pair_order[(index + attempt) % len(pair_order)]
            load_units = 8 + ((index * 7 + attempt * 3) % 25)
            priority = (Priority.HIGH, Priority.MEDIUM, Priority.LOW)[index % 3]
            candidate = Shipment(
                shipment_id=f"ASIA_S_{index + 1:04}",
                origin_location_id=factory.location_id,
                destination_location_id=customer.location_id,
                current_location_id=factory.location_id,
                priority=priority,
                required_delivery_time=base_time,
                current_eta=base_time,
                load_units=load_units,
                cargo_type=cargo_types[index % len(cargo_types)],
                source="SYNTHETIC",
            )
            paths = find_candidate_routes(graph, candidate, k=3)
            if not paths:
                continue
            selected = paths[0]
            departure = base_time + timedelta(hours=index * 6)
            arrival = departure + timedelta(hours=selected.duration_hours)
            status, current_index = _shipment_progress(index, len(selected.location_ids))
            route_legs = _route_legs(
                candidate.shipment_id,
                selected.location_ids,
                selected.route_ids,
                routes,
                departure,
                current_index,
                status,
            )
            current_location_id = _current_location(
                selected.location_ids,
                current_index,
                status,
            )
            shipments.append(
                candidate.model_copy(
                    update={
                        "current_location_id": current_location_id,
                        "required_delivery_time": arrival + timedelta(hours=48 + (index % 4) * 12),
                        "current_eta": arrival,
                        "status": status,
                        "route_legs": route_legs,
                        "order_id": f"ASIA_ORD_{index + 1:04}",
                        "customer_id": customer.location_id,
                    }
                )
            )
            pair_found = True
            break
        if not pair_found:
            raise ValueError(f"No feasible route found for generated shipment {index + 1}")
    return shipments


def _shipment_progress(index: int, path_length: int) -> tuple[str, int | None]:
    if index < 20:
        return "COMPLETED", None
    if index % 5 == 0:
        return "PLANNED", 0
    current_index = 1 + (index % max(1, path_length - 2))
    return ("AT_RISK" if index % 4 == 0 else "IN_TRANSIT"), current_index


def _current_location(path: list[str], current_index: int | None, status: str) -> str:
    if status == "COMPLETED":
        return path[-1]
    return path[current_index or 0]


def _route_legs(
    shipment_id: str,
    path: list[str],
    route_ids: list[str],
    routes: list[Route],
    departure: datetime,
    current_index: int | None,
    shipment_status: str,
) -> list[ShipmentRouteLeg]:
    routes_by_id = {route.route_id: route for route in routes}
    elapsed = 0.0
    legs = []
    for index, route_id in enumerate(route_ids):
        route = routes_by_id[route_id]
        planned_departure = departure + timedelta(hours=elapsed)
        planned_arrival = planned_departure + timedelta(hours=route.base_duration_hours)
        if shipment_status == "COMPLETED":
            status = "COMPLETED"
        elif current_index is None or index < current_index:
            status = "PLANNED"
        elif index == current_index:
            status = "CURRENT"
        else:
            status = "PLANNED"
        legs.append(
            ShipmentRouteLeg(
                shipment_id=shipment_id,
                sequence_no=index + 1,
                route_id=route_id,
                source_location_id=path[index],
                destination_location_id=path[index + 1],
                status=status,
                planned_departure=planned_departure,
                planned_arrival=planned_arrival,
                transport_mode=route.transport_mode,
            )
        )
        elapsed += route.base_duration_hours
    return legs


def _distance_km(source: Location, destination: Location) -> float:
    earth_radius = 6371.0
    lat1, lat2 = radians(source.latitude), radians(destination.latitude)
    delta_lat = radians(destination.latitude - source.latitude)
    delta_lon = radians(destination.longitude - source.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return earth_radius * 2 * asin(sqrt(value))


def _duration_hours(distance_km: float, mode: str) -> float:
    speed = 28 if mode == "SEA" else 55
    handling = 12 if mode == "SEA" else 2
    return round(max(2.0, distance_km / speed + handling), 2)


def validate_asia_dataset(dataset: RuntimeDataset) -> AsiaDatasetReport:
    locations = dataset.locations
    routes = dataset.routes
    shipments = dataset.shipments
    location_ids = {location.location_id for location in locations}
    route_ids = {route.route_id for route in routes}
    if len(location_ids) != len(locations):
        raise ValueError("Asia dataset contains duplicate location IDs")
    if len(route_ids) != len(routes):
        raise ValueError("Asia dataset contains duplicate route IDs")
    if any(location.latitude is None or location.longitude is None for location in locations):
        raise ValueError("Asia dataset contains a location without coordinates")
    if any(
        route.source_location_id not in location_ids
        or route.destination_location_id not in location_ids
        or route.max_capacity < 0
        for route in routes
    ):
        raise ValueError("Asia dataset contains an invalid route reference")

    graph = nx.DiGraph()
    graph.add_nodes_from(location_ids)
    graph.add_edges_from(
        (
            route.source_location_id,
            route.destination_location_id,
            {"route_id": route.route_id, "duration": route.base_duration_hours},
        )
        for route in routes
    )
    if any(
        shipment.origin_location_id not in location_ids
        or shipment.destination_location_id not in location_ids
        for shipment in shipments
    ):
        raise ValueError("Asia dataset contains an invalid shipment endpoint")
    routes_by_id = {route.route_id: route for route in routes}
    for shipment in shipments:
        legs = shipment.ordered_route_legs
        if not legs:
            raise ValueError(f"Shipment {shipment.shipment_id} has no route legs")
        if [leg.sequence_no for leg in legs] != list(range(1, len(legs) + 1)):
            raise ValueError(f"Shipment {shipment.shipment_id} has unordered route legs")
        for previous, current in zip(legs, legs[1:]):
            if previous.destination_location_id != current.source_location_id:
                raise ValueError(f"Shipment {shipment.shipment_id} has a broken route path")
        if legs[0].source_location_id != shipment.origin_location_id:
            raise ValueError(f"Shipment {shipment.shipment_id} starts off its origin")
        if legs[-1].destination_location_id != shipment.destination_location_id:
            raise ValueError(f"Shipment {shipment.shipment_id} does not reach its destination")
        for leg in legs:
            if leg.route_id not in route_ids or routes_by_id[leg.route_id].source_location_id != leg.source_location_id:
                raise ValueError(f"Shipment {shipment.shipment_id} references an invalid route leg")
        statuses = [leg.status for leg in legs]
        if shipment.status == "COMPLETED":
            if any(status != "COMPLETED" for status in statuses) or shipment.current_location_id != shipment.destination_location_id:
                raise ValueError(f"Completed shipment {shipment.shipment_id} has inconsistent progress")
        else:
            current_legs = [leg for leg in legs if leg.status == "CURRENT"]
            if shipment.current_location_id == shipment.origin_location_id:
                if len(current_legs) > 1:
                    raise ValueError(f"Shipment {shipment.shipment_id} has multiple current legs")
            elif len(current_legs) != 1 or current_legs[0].source_location_id != shipment.current_location_id:
                raise ValueError(f"Shipment {shipment.shipment_id} has inconsistent current progress")
        if not nx.has_path(graph, shipment.origin_location_id, shipment.destination_location_id):
            raise ValueError(f"Shipment {shipment.shipment_id} is disconnected")

    alternatives = 0
    for shipment in shipments:
        if len(_capacity_feasible_paths(graph, routes_by_id, shipment, 2)) >= 2:
            alternatives += 1
    return AsiaDatasetReport(
        real_ports=sum(location.source == "WPI" for location in locations),
        synthetic_factories=sum(location.location_type == LocationType.FACTORY for location in locations),
        synthetic_warehouses=sum(location.location_type == LocationType.WAREHOUSE for location in locations),
        synthetic_customers=sum(location.location_type == LocationType.CUSTOMER for location in locations),
        routes=len(routes),
        shipments=len(shipments),
        status_distribution=dict(sorted(Counter(shipment.status for shipment in shipments).items())),
        priority_distribution=dict(sorted(Counter(shipment.priority.value for shipment in shipments).items())),
        countries=tuple(sorted({location.country for location in locations})),
        connected_components=nx.number_connected_components(graph.to_undirected()),
        shipments_with_alternatives=alternatives,
    )


def _capacity_feasible_paths(
    graph: nx.DiGraph,
    routes_by_id: dict[str, Route],
    shipment: Shipment,
    limit: int,
) -> list[list[str]]:
    paths: list[list[str]] = []
    for path in nx.shortest_simple_paths(
        graph,
        shipment.origin_location_id,
        shipment.destination_location_id,
        weight="duration",
    ):
        route_ids = [graph[source][destination]["route_id"] for source, destination in zip(path, path[1:])]
        if all(routes_by_id[route_id].current_load + shipment.load_units <= routes_by_id[route_id].max_capacity for route_id in route_ids):
            paths.append(path)
        if len(paths) >= limit:
            break
    return paths


def report_asia_dataset(config: AsiaGenerationConfig | None = None) -> AsiaDatasetReport:
    return validate_asia_dataset(generate_asia_runtime_dataset(config))
