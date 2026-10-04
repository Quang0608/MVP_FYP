"""Curated, provider-neutral supply-chain corridor metadata."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NetworkZoneType(str, Enum):
    CHOKEPOINT = "CHOKEPOINT"
    ZONE = "ZONE"


class NetworkZonePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NetworkZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: NetworkZoneType
    aliases: list[str] = Field(default_factory=list)
    geometry: list[NetworkZonePoint] | None = None


NETWORK_ZONES: tuple[NetworkZone, ...] = (
    NetworkZone(
        id="CHK_SUEZ",
        name="Suez Canal",
        type=NetworkZoneType.CHOKEPOINT,
        aliases=["Suez", "Suez Canal chokepoint"],
        geometry=[NetworkZonePoint(latitude=30.5, longitude=32.3)],
    ),
    NetworkZone(
        id="CHK_MALACCA",
        name="Strait of Malacca",
        type=NetworkZoneType.CHOKEPOINT,
        aliases=["Malacca Strait", "Malacca"],
        geometry=[NetworkZonePoint(latitude=2.5, longitude=101.0)],
    ),
    NetworkZone(
        id="CHK_HORMUZ",
        name="Strait of Hormuz",
        type=NetworkZoneType.CHOKEPOINT,
        aliases=["Hormuz"],
        geometry=[NetworkZonePoint(latitude=26.5, longitude=56.3)],
    ),
    NetworkZone(
        id="ZONE_SOUTH_CHINA_SEA",
        name="South China Sea",
        type=NetworkZoneType.ZONE,
        aliases=["South China Sea region"],
        geometry=[NetworkZonePoint(latitude=14.0, longitude=114.0)],
    ),
    NetworkZone(
        id="ZONE_RED_SEA",
        name="Red Sea",
        type=NetworkZoneType.ZONE,
        aliases=["Red Sea region"],
        geometry=[NetworkZonePoint(latitude=20.0, longitude=38.0)],
    ),
    NetworkZone(
        id="ZONE_INDIAN_OCEAN",
        name="Indian Ocean",
        type=NetworkZoneType.ZONE,
        aliases=["Indian Ocean region"],
        geometry=[NetworkZonePoint(latitude=8.0, longitude=78.0)],
    ),
    NetworkZone(
        id="ZONE_CAPE_GOOD_HOPE",
        name="Cape of Good Hope",
        type=NetworkZoneType.ZONE,
        aliases=["Cape route", "Cape of Good Hope route"],
        geometry=[NetworkZonePoint(latitude=-34.4, longitude=18.5)],
    ),
)


PORT_PAIR_CORRIDOR_MEMBERSHIPS: dict[tuple[str, str], tuple[str, ...]] = {
    ("LOC_WPI_50000", "LOC_WPI_49930"): (
        "CHK_MALACCA",
        "ZONE_SOUTH_CHINA_SEA",
    ),
    ("LOC_WPI_50000", "LOC_WPI_51587"): (
        "CHK_MALACCA",
        "ZONE_SOUTH_CHINA_SEA",
    ),
    ("LOC_WPI_50000", "LOC_WPI_48840"): (
        "CHK_MALACCA",
        "ZONE_INDIAN_OCEAN",
        "ZONE_RED_SEA",
        "CHK_SUEZ",
    ),
    ("LOC_WPI_49930", "LOC_WPI_48840"): (
        "CHK_MALACCA",
        "ZONE_INDIAN_OCEAN",
        "ZONE_RED_SEA",
        "CHK_SUEZ",
    ),
    ("LOC_WPI_49450", "LOC_WPI_48840"): (
        "ZONE_INDIAN_OCEAN",
        "ZONE_RED_SEA",
        "CHK_SUEZ",
    ),
    ("LOC_WPI_48617", "LOC_WPI_49240"): (
        "ZONE_INDIAN_OCEAN",
        "CHK_HORMUZ",
    ),
    ("LOC_WPI_49240", "LOC_WPI_50970"): (
        "ZONE_INDIAN_OCEAN",
        "ZONE_CAPE_GOOD_HOPE",
    ),
}


def get_network_zones() -> list[NetworkZone]:
    """Return independent copies so callers cannot mutate the catalog."""

    return [zone.model_copy(deep=True) for zone in NETWORK_ZONES]


def corridor_memberships_for_route(
    source_location_id: str,
    destination_location_id: str,
    transport_mode: str,
) -> list[str]:
    """Return deterministic metadata for a directed route pair."""

    if transport_mode.upper() != "SEA":
        return []
    explicit = PORT_PAIR_CORRIDOR_MEMBERSHIPS.get(
        (source_location_id, destination_location_id)
    )
    if explicit is not None:
        return list(explicit)
    return ["ZONE_SOUTH_CHINA_SEA"]
