import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings
from .domain import (
    Location,
    LocationType,
    Priority,
    Route,
    RuntimeDataset,
    Shipment,
    ShipmentRouteLeg,
    Status,
    WeatherSamplePoint,
)
from .schemas import Disruption, DisruptionRequest


class Base(DeclarativeBase):
    pass


class LegacyBase(DeclarativeBase):
    pass


class LocationRecord(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_location_id: Mapped[str | None] = mapped_column(String, nullable=True)
    unlocode: Mapped[str | None] = mapped_column(String, nullable=True)
    source_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)


class RouteRecord(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    destination_location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    normal_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    current_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    current_load: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    source_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    corridor_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_sample_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ShipmentRecord(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    origin_id: Mapped[str] = mapped_column(ForeignKey("locations.id"), nullable=False)
    destination_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    current_location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    load_units: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    current_eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cargo_type: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class ShipmentRouteLegRecord(Base):
    __tablename__ = "shipment_route_legs"

    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), nullable=False)
    source_location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    destination_location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    planned_departure: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transport_mode: Mapped[str | None] = mapped_column(String, nullable=True)


class DisruptionRecord(Base):
    __tablename__ = "disruptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    disruption_type: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    estimated_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DisruptionLocationRecord(Base):
    __tablename__ = "disruption_locations"

    disruption_id: Mapped[str] = mapped_column(
        ForeignKey("disruptions.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.id"), primary_key=True
    )


class DisruptionRouteRecord(Base):
    __tablename__ = "disruption_routes"

    disruption_id: Mapped[str] = mapped_column(
        ForeignKey("disruptions.id", ondelete="CASCADE"), primary_key=True
    )
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), primary_key=True)


class SimulationRunRecord(Base):
    __tablename__ = "simulation_runs"

    disruption_id: Mapped[str] = mapped_column(
        ForeignKey("disruptions.id", ondelete="CASCADE"), primary_key=True
    )
    simulation_result: Mapped[str] = mapped_column(Text, nullable=False)
    reroute_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AgentDecisionRecord(Base):
    __tablename__ = "agent_decisions"
    __table_args__ = (
        UniqueConstraint(
            "disruption_id", "shipment_id", name="uq_agent_decision_disruption_shipment"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disruption_id: Mapped[str] = mapped_column(
        ForeignKey("disruptions.id", ondelete="CASCADE"), nullable=False
    )
    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    original_route: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_route: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_delay_saved: Mapped[float] = mapped_column(Float, nullable=False)
    additional_cost: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LegacyRunRecord(LegacyBase):
    """Read-only compatibility model for databases created before ISS-0007."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    disruption: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _weather_sample_points(value: str | None) -> list[WeatherSamplePoint]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [WeatherSamplePoint.model_validate(item) for item in parsed]


if settings.database_url == "sqlite://":
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(settings.database_url, connect_args=connect_args)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


Session = sessionmaker(bind=engine, expire_on_commit=False)


def initialise_database() -> None:
    Base.metadata.create_all(engine)
    _ensure_runtime_columns()
    seed_master_data()


def _ensure_runtime_columns() -> None:
    """Add Phase 4 provenance/progress columns to an existing local SQLite DB."""

    if not settings.database_url.startswith("sqlite"):
        return
    additions = {
        "locations": {
            "source": "VARCHAR",
            "canonical_location_id": "VARCHAR",
            "unlocode": "VARCHAR",
            "source_entity_id": "VARCHAR",
        },
        "routes": {
            "distance_km": "FLOAT",
            "source": "VARCHAR",
            "source_entity_id": "VARCHAR",
            "corridor_ids_json": "TEXT",
            "weather_sample_points_json": "TEXT",
        },
        "shipments": {
            "current_eta": "DATETIME",
            "cargo_type": "VARCHAR",
            "source": "VARCHAR",
        },
        "shipment_route_legs": {
            "status": "VARCHAR",
            "planned_departure": "DATETIME",
            "planned_arrival": "DATETIME",
            "transport_mode": "VARCHAR",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, sql_type in columns.items():
                if column not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
                    )


def seed_master_data() -> None:
    from .asia_dataset import generate_asia_runtime_dataset

    with Session() as session:
        if session.scalar(
            select(ShipmentRecord.id).where(ShipmentRecord.id.like("ASIA_S_%")).limit(1)
        ) is not None:
            _backfill_route_exposure_metadata(session)
            return

        dataset = generate_asia_runtime_dataset()
        locations, routes, shipments = (
            dataset.locations,
            dataset.routes,
            dataset.shipments,
        )
        session.add_all(
            [
                LocationRecord(
                    id=location.id,
                    name=location.name,
                    type=location.type.value,
                    country=location.country,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    status=location.status.value,
                    capacity=location.capacity,
                    source=location.source,
                    canonical_location_id=location.canonical_location_id,
                    unlocode=location.unlocode,
                    source_entity_id=location.source_entity_id,
                )
                for location in locations
            ]
        )
        session.add_all(
            [
                RouteRecord(
                    id=route.id,
                    source_location_id=route.source_location_id,
                    destination_location_id=route.destination_location_id,
                    mode=route.mode,
                    normal_duration_hours=route.normal_duration_hours,
                    current_duration_hours=route.current_duration_hours,
                    cost=route.cost,
                    risk_score=route.risk_score,
                    capacity=route.capacity,
                    current_load=route.current_load,
                    status=route.status.value,
                    distance_km=route.distance_km,
                    source=route.source,
                    source_entity_id=route.source_entity_id,
                    corridor_ids_json=json.dumps(
                        route.corridor_ids,
                        sort_keys=True,
                    ),
                    weather_sample_points_json=json.dumps(
                        [
                            point.model_dump(mode="json")
                            for point in route.weather_sample_points
                        ],
                        sort_keys=True,
                    ),
                )
                for route in routes
            ]
        )
        session.add_all(
            [
                ShipmentRecord(
                    id=shipment.id,
                    origin_id=shipment.origin_id,
                    destination_id=shipment.destination_id,
                    current_location_id=shipment.current_location_id,
                    deadline=shipment.deadline,
                    priority=shipment.priority.value,
                    load_units=shipment.load_units,
                    status=shipment.status,
                    current_eta=shipment.current_eta,
                    cargo_type=shipment.cargo_type,
                    source=shipment.source,
                )
                for shipment in shipments
            ]
        )
        route_by_id = {route.id: route for route in routes}
        for shipment in shipments:
            for sequence, leg in enumerate(shipment.ordered_route_legs, start=1):
                route_id = leg.route_id
                route = route_by_id[route_id]
                session.add(
                    ShipmentRouteLegRecord(
                        shipment_id=shipment.id,
                        sequence=sequence,
                        route_id=route_id,
                        source_location_id=route.source_location_id,
                        destination_location_id=route.destination_location_id,
                        status=leg.status,
                        planned_departure=leg.planned_departure,
                        planned_arrival=leg.planned_arrival,
                        transport_mode=leg.transport_mode,
                    )
                )
        session.commit()


def _backfill_route_exposure_metadata(session) -> None:
    """Add Phase 4.1 metadata to an existing Asia route table once."""

    rows = session.scalars(
        select(RouteRecord).where(RouteRecord.id.like("ASIA_R_%"))
    ).all()
    missing_metadata = any(
        row.corridor_ids_json is None or row.weather_sample_points_json is None
        for row in rows
    )
    if not missing_metadata:
        return

    from .asia_dataset import generate_asia_runtime_dataset

    metadata_by_id = {
        route.route_id: route
        for route in generate_asia_runtime_dataset().routes
    }
    changed = False
    for row in rows:
        route = metadata_by_id.get(row.id)
        if route is None:
            continue
        if row.corridor_ids_json is None:
            row.corridor_ids_json = json.dumps(route.corridor_ids, sort_keys=True)
            changed = True
        if row.weather_sample_points_json is None:
            row.weather_sample_points_json = json.dumps(
                [point.model_dump(mode="json") for point in route.weather_sample_points],
                sort_keys=True,
            )
            changed = True
    if changed:
        session.commit()


def load_runtime_dataset() -> RuntimeDataset:
    with Session() as session:
        location_rows = session.scalars(
            select(LocationRecord).order_by(LocationRecord.id)
        ).all()
        route_rows = session.scalars(select(RouteRecord).order_by(RouteRecord.id)).all()
        shipment_rows = session.scalars(
            select(ShipmentRecord).order_by(ShipmentRecord.id)
        ).all()
        leg_rows = session.scalars(
            select(ShipmentRouteLegRecord).order_by(
                ShipmentRouteLegRecord.shipment_id,
                ShipmentRouteLegRecord.sequence,
            )
        ).all()

    location_rows = [
        row
        for row in location_rows
        if row.id.startswith("LOC_WPI_") or row.id.startswith("ASIA_")
    ]
    route_rows = [row for row in route_rows if row.id.startswith("ASIA_R_")]
    shipment_rows = [row for row in shipment_rows if row.id.startswith("ASIA_S_")]
    shipment_ids = {row.id for row in shipment_rows}
    leg_rows = [row for row in leg_rows if row.shipment_id in shipment_ids]

    locations = [
        Location(
            location_id=row.id,
            name=row.name,
            location_type=LocationType(row.type),
            country=row.country,
            latitude=row.latitude,
            longitude=row.longitude,
            status=Status(row.status),
            capacity=row.capacity,
            source=row.source or ("WPI" if row.id.startswith("LOC_WPI_") else "SYNTHETIC"),
            canonical_location_id=row.canonical_location_id,
            unlocode=row.unlocode,
            source_entity_id=row.source_entity_id or row.id,
        )
        for row in location_rows
    ]
    routes = [
        Route(
            route_id=row.id,
            source_location_id=row.source_location_id,
            destination_location_id=row.destination_location_id,
            transport_mode=row.mode,
            base_duration_hours=row.normal_duration_hours,
            base_cost=row.cost,
            max_capacity=row.capacity,
            risk_score=row.risk_score,
            current_load=row.current_load,
            status=Status(row.status),
            distance_km=row.distance_km or 0,
            source=row.source or "DERIVED_SYNTHETIC",
            source_entity_id=row.source_entity_id or row.id,
            corridor_ids=_json_list(row.corridor_ids_json),
            weather_sample_points=_weather_sample_points(
                row.weather_sample_points_json
            ),
        )
        for row in route_rows
    ]

    legs_by_shipment: dict[str, list[ShipmentRouteLegRecord]] = {}
    for leg in leg_rows:
        legs_by_shipment.setdefault(leg.shipment_id, []).append(leg)

    route_by_id = {route.route_id: route for route in routes}
    shipments = []
    for row in shipment_rows:
        legs = legs_by_shipment.get(row.id, [])
        sequence_offset = 1 if legs and min(leg.sequence for leg in legs) == 0 else 0
        current_leg_index: int | None = None
        for index, leg in enumerate(legs):
            if leg.source_location_id == row.current_location_id:
                current_leg_index = index
                break
            if leg.destination_location_id == row.current_location_id:
                current_leg_index = index + 1
                break
        canonical_legs = []
        for index, leg in enumerate(legs):
            route = route_by_id[leg.route_id]
            sequence_no = leg.sequence + sequence_offset
            if current_leg_index is not None and index < current_leg_index:
                leg_status = "COMPLETED"
            elif current_leg_index is not None and index == current_leg_index:
                leg_status = "CURRENT"
            else:
                leg_status = "PLANNED"
            canonical_legs.append(
                ShipmentRouteLeg(
                    shipment_id=row.id,
                    sequence_no=sequence_no,
                    route_id=leg.route_id,
                    source_location_id=leg.source_location_id,
                    destination_location_id=leg.destination_location_id,
                    status=leg.status or leg_status,
                    planned_departure=leg.planned_departure,
                    planned_arrival=leg.planned_arrival,
                    transport_mode=leg.transport_mode or route.transport_mode,
                )
            )
        shipments.append(
            Shipment(
                shipment_id=row.id,
                origin_location_id=row.origin_id,
                destination_location_id=row.destination_id,
                current_location_id=row.current_location_id,
                required_delivery_time=row.deadline,
                current_eta=row.current_eta or row.deadline,
                priority=Priority(row.priority),
                load_units=row.load_units,
                cargo_type=row.cargo_type or "GENERAL",
                status=row.status,
                route_legs=canonical_legs,
                order_id=f"ORD_{row.id}",
                customer_id=row.destination_id,
                source=row.source or "SYNTHETIC",
            )
        )
    return RuntimeDataset(
        locations=locations,
        routes=routes,
        shipments=shipments,
    )


def load_supply_chain_data() -> tuple[list[Location], list[Route], list[Shipment]]:
    """Compatibility tuple wrapper around the canonical repository snapshot."""

    dataset = load_runtime_dataset()
    return dataset.locations, dataset.routes, dataset.shipments


def save_disruption(disruption: Disruption, simulation_result: dict) -> None:
    request = disruption.request
    start_time = disruption.created_at
    estimated_end_time = start_time + timedelta(hours=request.duration_hours)

    with Session() as session:
        disruption_record = DisruptionRecord(
            id=disruption.id,
            disruption_type=request.disruption_type.value,
            start_time=start_time,
            estimated_end_time=estimated_end_time,
            duration_hours=request.duration_hours,
            severity=request.severity,
            description=request.description,
            created_at=disruption.created_at,
        )
        session.add(disruption_record)
        session.flush()
        session.add_all(
            [
                DisruptionLocationRecord(
                    disruption_id=disruption.id,
                    location_id=location_id,
                )
                for location_id in request.affected_location_ids
            ]
        )
        session.add_all(
            [
                DisruptionRouteRecord(
                    disruption_id=disruption.id,
                    route_id=route_id,
                )
                for route_id in request.affected_route_ids
            ]
        )
        session.add(
            SimulationRunRecord(
                disruption_id=disruption.id,
                simulation_result=json.dumps(simulation_result),
                reroute_result=None,
                metrics=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def save_agent_decisions(disruption_id: str, reroute_result: dict) -> None:
    recommendations = reroute_result.get("recommendations", [])
    now = datetime.now(timezone.utc)

    with Session() as session:
        run = session.get(SimulationRunRecord, disruption_id)
        if run is None:
            run = _migrate_legacy_run_for_write(session, disruption_id)

        existing = session.scalars(
            select(AgentDecisionRecord).where(
                AgentDecisionRecord.disruption_id == disruption_id
            )
        ).all()
        for record in existing:
            session.delete(record)

        for recommendation in recommendations:
            selected_route = recommendation.get("selected_route")
            reason = (
                "Selected the highest-ranked capacity-feasible route."
                if selected_route
                else "No capacity-feasible alternative route was available."
            )
            session.add(
                AgentDecisionRecord(
                    disruption_id=disruption_id,
                    shipment_id=recommendation["shipment_id"],
                    status=recommendation["status"],
                    original_route=_dump_optional(recommendation.get("original_route")),
                    alternative_route=_dump_optional(selected_route),
                    estimated_delay_saved=recommendation.get(
                        "delay_saved_hours", 0
                    ),
                    additional_cost=recommendation.get("additional_cost", 0),
                    risk_score=(
                        selected_route.get("risk_score") if selected_route else None
                    ),
                    route_score=(
                        selected_route.get("route_score") if selected_route else None
                    ),
                    reason=reason,
                    confidence_score=None,
                    llm_explanation=None,
                    decision_payload=json.dumps(recommendation),
                    created_at=now,
                )
            )

        run.reroute_result = json.dumps(reroute_result)
        run.metrics = json.dumps(reroute_result.get("metrics"))
        run.updated_at = now
        session.commit()


def save_decision_explanation(
    disruption_id: str, shipment_id: str, explanation: dict
) -> None:
    with Session() as session:
        decision = session.scalar(
            select(AgentDecisionRecord).where(
                AgentDecisionRecord.disruption_id == disruption_id,
                AgentDecisionRecord.shipment_id == shipment_id,
            )
        )
        if decision is None:
            raise ValueError(
                f"Agent decision for disruption {disruption_id} and "
                f"shipment {shipment_id} does not exist"
            )
        decision.llm_explanation = json.dumps(explanation)
        session.commit()


def get_run(run_id: str) -> dict | None:
    with Session() as session:
        disruption = session.get(DisruptionRecord, run_id)
        if disruption is not None:
            request = _load_disruption_request(session, disruption)
            run = session.get(SimulationRunRecord, run_id)
            results = {}
            if run is not None:
                stored_result = run.reroute_result or run.simulation_result
                results = json.loads(stored_result)
            return {
                "disruption": {
                    "id": disruption.id,
                    "request": request.model_dump(mode="json"),
                    "created_at": disruption.created_at.isoformat(),
                },
                "results": results,
            }

        if not inspect(engine).has_table("runs"):
            return None
        legacy = session.get(LegacyRunRecord, run_id)
        if legacy is None:
            return None
        return {
            "disruption": json.loads(legacy.disruption),
            "results": json.loads(legacy.results),
        }


def all_runs() -> list[dict]:
    with Session() as session:
        structured = []
        disruptions = session.scalars(
            select(DisruptionRecord).order_by(DisruptionRecord.created_at)
        ).all()
        structured_ids = {disruption.id for disruption in disruptions}
        for disruption in disruptions:
            run = session.get(SimulationRunRecord, disruption.id)
            results = {}
            if run is not None:
                stored_result = run.reroute_result or run.simulation_result
                results = json.loads(stored_result)
            request = _load_disruption_request(session, disruption)
            structured.append(
                {
                    "id": disruption.id,
                    "created_at": disruption.created_at,
                    "disruption": request.model_dump(mode="json"),
                    "results": results,
                }
            )

        legacy_rows = []
        if inspect(engine).has_table("runs"):
            legacy_rows = session.scalars(
                select(LegacyRunRecord).order_by(LegacyRunRecord.created_at)
            ).all()
        legacy = [
            {
                "id": row.id,
                "created_at": row.created_at,
                "disruption": json.loads(row.disruption).get("request"),
                "results": json.loads(row.results),
            }
            for row in legacy_rows
            if row.id not in structured_ids
        ]
        return legacy + structured


def _load_disruption_request(
    session, disruption: DisruptionRecord
) -> DisruptionRequest:
    location_ids = session.scalars(
        select(DisruptionLocationRecord.location_id).where(
            DisruptionLocationRecord.disruption_id == disruption.id
        )
    ).all()
    route_ids = session.scalars(
        select(DisruptionRouteRecord.route_id).where(
            DisruptionRouteRecord.disruption_id == disruption.id
        )
    ).all()
    return DisruptionRequest(
        disruption_type=disruption.disruption_type,
        affected_location_ids=list(location_ids),
        affected_route_ids=list(route_ids),
        duration_hours=disruption.duration_hours,
        severity=disruption.severity,
        description=disruption.description,
    )


def _dump_optional(value: dict | None) -> str | None:
    return json.dumps(value) if value is not None else None


def _migrate_legacy_run_for_write(
    session, disruption_id: str
) -> SimulationRunRecord:
    if not inspect(engine).has_table("runs"):
        raise ValueError(f"Simulation run {disruption_id} does not exist")

    legacy = session.get(LegacyRunRecord, disruption_id)
    if legacy is None:
        raise ValueError(f"Simulation run {disruption_id} does not exist")

    disruption = Disruption.model_validate(json.loads(legacy.disruption))
    request = disruption.request
    session.add(
        DisruptionRecord(
            id=disruption.id,
            disruption_type=request.disruption_type.value,
            start_time=disruption.created_at,
            estimated_end_time=(
                disruption.created_at + timedelta(hours=request.duration_hours)
            ),
            duration_hours=request.duration_hours,
            severity=request.severity,
            description=request.description,
            created_at=disruption.created_at,
        )
    )
    session.flush()
    session.add_all(
        [
            DisruptionLocationRecord(
                disruption_id=disruption.id,
                location_id=location_id,
            )
            for location_id in request.affected_location_ids
        ]
    )
    session.add_all(
        [
            DisruptionRouteRecord(
                disruption_id=disruption.id,
                route_id=route_id,
            )
            for route_id in request.affected_route_ids
        ]
    )
    run = SimulationRunRecord(
        disruption_id=disruption.id,
        simulation_result=legacy.results,
        reroute_result=None,
        metrics=None,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run
