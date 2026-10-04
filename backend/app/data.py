from datetime import datetime, timedelta, timezone
from .domain import Location, LocationType, Priority, Route, Shipment, ShipmentRouteLeg


def seed_data() -> tuple[list[Location], list[Route], list[Shipment]]:
    locations = [
        ("F_SZ", "Shenzhen Factory", LocationType.FACTORY, "China", 22.54, 114.06),
        ("F_HCM", "Ho Chi Minh Factory", LocationType.FACTORY, "Vietnam", 10.82, 106.63),
        ("F_BKK", "Bangkok Factory", LocationType.FACTORY, "Thailand", 13.75, 100.50),
        ("P_SG", "Singapore Port", LocationType.PORT, "Singapore", 1.26, 103.82),
        ("P_KL", "Port Klang", LocationType.PORT, "Malaysia", 3.00, 101.38),
        ("P_TP", "Tanjung Pelepas Port", LocationType.PORT, "Malaysia", 1.36, 103.55),
        ("P_LC", "Laem Chabang Port", LocationType.PORT, "Thailand", 13.08, 100.88),
        ("W_SG", "Singapore Warehouse", LocationType.WAREHOUSE, "Singapore", 1.35, 103.82),
        ("W_MY", "Malaysia Warehouse", LocationType.WAREHOUSE, "Malaysia", 3.14, 101.69),
        ("W_AU", "Australia Warehouse", LocationType.WAREHOUSE, "Australia", -33.87, 151.21),
        ("C_A", "Customer A", LocationType.CUSTOMER, "Singapore", 1.31, 103.85),
        ("C_B", "Customer B", LocationType.CUSTOMER, "Malaysia", 3.15, 101.71),
        ("C_C", "Customer C", LocationType.CUSTOMER, "Australia", -37.81, 144.96),
    ]
    location_records = [
        Location(
            location_id=location_id,
            name=name,
            location_type=location_type,
            country=country,
            latitude=latitude,
            longitude=longitude,
            capacity=500,
            source="SYNTHETIC",
            source_entity_id=location_id,
        )
        for location_id, name, location_type, country, latitude, longitude in locations
    ]
    rows = [
        ("R1", "F_SZ", "P_SG", "SEA", 48, 900, .2), ("R2", "F_SZ", "P_KL", "SEA", 54, 850, .25),
        ("R3", "F_HCM", "P_SG", "SEA", 36, 700, .2), ("R4", "F_HCM", "P_TP", "SEA", 40, 650, .22),
        ("R5", "F_BKK", "P_LC", "ROAD", 12, 350, .15), ("R6", "P_LC", "P_SG", "SEA", 42, 750, .28),
        ("R7", "P_KL", "P_TP", "SEA", 8, 180, .12), ("R8", "P_TP", "W_SG", "SEA", 10, 250, .18),
        ("R9", "P_SG", "W_SG", "ROAD", 6, 180, .1), ("R10", "P_KL", "W_MY", "ROAD", 7, 170, .12),
        ("R11", "P_TP", "W_MY", "ROAD", 8, 190, .14), ("R12", "W_SG", "C_A", "ROAD", 3, 80, .05),
        ("R13", "W_MY", "C_B", "ROAD", 3, 80, .05), ("R14", "P_SG", "W_AU", "SEA", 110, 1800, .3),
        ("R15", "P_KL", "W_AU", "SEA", 118, 1700, .32), ("R16", "W_AU", "C_C", "ROAD", 5, 120, .06),
        ("R17", "P_LC", "P_KL", "SEA", 28, 500, .24),
    ]
    route_records = [
        Route(
            route_id=route_id,
            source_location_id=source_id,
            destination_location_id=destination_id,
            transport_mode=mode,
            distance_km=duration * (35 if mode == "SEA" else 8),
            base_duration_hours=duration,
            base_cost=cost,
            max_capacity=100,
            risk_score=risk,
            current_load=20,
        )
        for route_id, source_id, destination_id, mode, duration, cost, risk in rows
    ]
    templates=[("F_SZ","C_A",["F_SZ","P_SG","W_SG","C_A"],["R1","R9","R12"]),("F_SZ","C_B",["F_SZ","P_KL","W_MY","C_B"],["R2","R10","R13"]),("F_HCM","C_A",["F_HCM","P_SG","W_SG","C_A"],["R3","R9","R12"]),("F_HCM","C_B",["F_HCM","P_TP","W_MY","C_B"],["R4","R11","R13"]),("F_BKK","C_C",["F_BKK","P_LC","P_SG","W_AU","C_C"],["R5","R6","R14","R16"]),("F_SZ","C_C",["F_SZ","P_KL","W_AU","C_C"],["R2","R15","R16"])]
    route_by_id = {route.route_id: route for route in route_records}
    base_time = datetime.now(timezone.utc) + timedelta(days=10)
    shipment_records = []
    for index in range(30):
        origin_id, destination_id, nodes, route_ids = templates[index % len(templates)]
        departure = base_time + timedelta(hours=index)
        elapsed_hours = 0.0
        legs = []
        for sequence_no, route_id in enumerate(route_ids, start=1):
            route = route_by_id[route_id]
            arrival = departure + timedelta(hours=elapsed_hours + route.base_duration_hours)
            leg_status = "CURRENT" if sequence_no == 1 else "PLANNED"
            legs.append(
                ShipmentRouteLeg(
                    shipment_id=f"S{index + 1:03}",
                    sequence_no=sequence_no,
                    route_id=route_id,
                    source_location_id=route.source_location_id,
                    destination_location_id=route.destination_location_id,
                    status=leg_status,
                    planned_departure=departure + timedelta(hours=elapsed_hours),
                    planned_arrival=arrival,
                    transport_mode=route.transport_mode,
                )
            )
            elapsed_hours += route.base_duration_hours
        shipment_records.append(
            Shipment(
                shipment_id=f"S{index + 1:03}",
                origin_location_id=origin_id,
                destination_location_id=destination_id,
                current_location_id=origin_id,
                priority=[Priority.HIGH, Priority.MEDIUM, Priority.LOW][index % 3],
                required_delivery_time=departure + timedelta(hours=elapsed_hours + 24),
                current_eta=departure + timedelta(hours=elapsed_hours),
                load_units=5 + (index % 4) * 5,
                cargo_type="GENERAL",
                status="ON_TIME",
                route_legs=legs,
                order_id=f"ORD{index + 1:03}",
                customer_id=destination_id,
            )
        )
    return location_records, route_records, shipment_records


SCENARIOS = {
 "singapore_closure": {"disruption_type":"PORT_CLOSURE","affected_location_ids":["LOC_WPI_50000"],"duration_hours":72,"severity":"HIGH"},
 "klang_congestion": {"disruption_type":"CONGESTION","affected_location_ids":["LOC_WPI_49930"],"duration_hours":48,"severity":"MEDIUM"},
 "shenzhen_shutdown": {"disruption_type":"FACTORY_SHUTDOWN","affected_location_ids":["ASIA_F_002"],"duration_hours":48,"severity":"HIGH"},
 "klang_road_block": {"disruption_type":"ROUTE_BLOCKED","affected_route_ids":["ASIA_R_0003"],"duration_hours":24,"severity":"HIGH"},
 "multiple_ports": {"disruption_type":"MULTIPLE_PORT","affected_location_ids":["LOC_WPI_50000","LOC_WPI_49930"],"duration_hours":72,"severity":"HIGH"},
}
