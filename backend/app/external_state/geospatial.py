"""Small deterministic geospatial helpers for route-exposure matching."""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from ..domain import Location, Route, WeatherSamplePoint


@dataclass(frozen=True)
class SamplePointMatch:
    route_id: str
    sequence: int
    distance_km: float


def haversine_km(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    """Return the great-circle distance between two latitude/longitude pairs."""

    earth_radius_km = 6371.0
    latitude_one = radians(first_latitude)
    latitude_two = radians(second_latitude)
    delta_latitude = radians(second_latitude - first_latitude)
    delta_longitude = radians(second_longitude - first_longitude)
    value = (
        sin(delta_latitude / 2) ** 2
        + cos(latitude_one)
        * cos(latitude_two)
        * sin(delta_longitude / 2) ** 2
    )
    return earth_radius_km * 2 * asin(sqrt(min(1.0, value)))


def interpolate_weather_sample_points(
    source: Location,
    destination: Location,
    count: int = 5,
) -> list[WeatherSamplePoint]:
    """Create representative, non-navigational points along a SEA edge."""

    if not 3 <= count <= 5:
        raise ValueError("Maritime route sample points must contain 3 to 5 points")
    denominator = count - 1
    return [
        WeatherSamplePoint(
            sequence=index + 1,
            latitude=source.latitude
            + (destination.latitude - source.latitude) * index / denominator,
            longitude=source.longitude
            + (destination.longitude - source.longitude) * index / denominator,
        )
        for index in range(count)
    ]


def match_route_sample_points(
    routes: list[Route],
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[SamplePointMatch]:
    """Return every route sample inside the configured radius."""

    matches: list[SamplePointMatch] = []
    for route in routes:
        for point in route.weather_sample_points:
            distance = haversine_km(
                latitude,
                longitude,
                point.latitude,
                point.longitude,
            )
            if distance <= radius_km:
                matches.append(
                    SamplePointMatch(
                        route_id=route.route_id,
                        sequence=point.sequence,
                        distance_km=round(distance, 3),
                    )
                )
    return sorted(
        matches,
        key=lambda match: (match.route_id, match.sequence, match.distance_km),
    )
