"""Application wiring for the provider-isolated weather service."""

from __future__ import annotations

from pathlib import Path

from ...config import Settings
from ...domain import Route
from .cache import WeatherCache
from .open_meteo_client import OpenMeteoClient
from .service import WeatherService
from .snapshots import RawWeatherSnapshotStore


def build_weather_service(routes: list[Route], settings: Settings) -> WeatherService:
    client = OpenMeteoClient(
        forecast_base_url=settings.open_meteo_forecast_base_url,
        marine_base_url=settings.open_meteo_marine_base_url,
        timeout_seconds=settings.open_meteo_request_timeout_seconds,
        retry_count=settings.open_meteo_retry_count,
    )
    return WeatherService(
        routes=routes,
        client=client,
        cache=WeatherCache(
            Path(settings.open_meteo_cache_directory),
            settings.open_meteo_cache_ttl_minutes,
        ),
        snapshots=RawWeatherSnapshotStore(
            Path(settings.open_meteo_raw_snapshot_directory)
        ),
        enabled=settings.open_meteo_enabled,
        max_coordinates_per_request=settings.open_meteo_max_coordinates_per_request,
        application_environment=settings.app_env,
    )
