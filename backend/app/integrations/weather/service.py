"""Route/sample-point orchestration for raw Open-Meteo retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any

from ...domain import Route
from .cache import WeatherCache, make_weather_cache_key
from .errors import UnsupportedWeatherRoute, WeatherProviderError
from .open_meteo_client import (
    FORECAST_VARIABLES,
    MARINE_VARIABLES,
    OpenMeteoClient,
)
from .schemas import (
    ForecastWindow,
    OpenMeteoBatchResponse,
    RouteWeatherRawResult,
    WeatherCacheStatus,
    WeatherCoordinate,
)
from .snapshots import RawWeatherSnapshotStore


class WeatherService:
    """Fetch one SEA route's geographic weather evidence as a batched operation."""

    def __init__(
        self,
        *,
        routes: list[Route],
        client: OpenMeteoClient,
        cache: WeatherCache,
        snapshots: RawWeatherSnapshotStore,
        enabled: bool = True,
        max_coordinates_per_request: int = 50,
        application_environment: str = "local-mvp",
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if max_coordinates_per_request <= 0:
            raise ValueError("max_coordinates_per_request must be positive")
        self._routes = {route.route_id: route for route in routes}
        self._client = client
        self._cache = cache
        self._snapshots = snapshots
        self._enabled = enabled
        self._max_coordinates = max_coordinates_per_request
        self._application_environment = application_environment
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    def close(self) -> None:
        self._client.close()

    def get_route_weather_raw(
        self,
        route_id: str,
        forecast_window: ForecastWindow | None = None,
    ) -> RouteWeatherRawResult:
        if not self._enabled:
            raise WeatherProviderError("Open-Meteo integration is disabled")
        route = self._routes.get(route_id)
        if route is None:
            raise UnsupportedWeatherRoute(f"Unknown weather route: {route_id}")
        if route.transport_mode.upper() != "SEA":
            raise UnsupportedWeatherRoute(
                f"Weather retrieval only supports SEA routes: {route_id}"
            )
        if not route.weather_sample_points:
            raise UnsupportedWeatherRoute(
                f"SEA route has no weather sample points: {route_id}"
            )

        window = forecast_window or ForecastWindow()
        coordinates = [
            WeatherCoordinate(latitude=point.latitude, longitude=point.longitude)
            for point in sorted(route.weather_sample_points, key=lambda item: item.sequence)
        ]
        weather_response, weather_status, weather_live = self._get_api_response(
            api_type="forecast",
            coordinates=coordinates,
            variables=FORECAST_VARIABLES,
            forecast_window=window,
        )
        marine_response, marine_status, marine_live = self._get_api_response(
            api_type="marine",
            coordinates=coordinates,
            variables=MARINE_VARIABLES,
            forecast_window=window,
        )

        retrieved_at = self._as_utc(self._now())
        snapshot_path: Path | None = None
        if weather_live or marine_live:
            snapshot_path = self._snapshots.save(
                route_id=route_id,
                retrieved_at=retrieved_at,
                forecast_payload=weather_response.raw_payload,
                marine_payload=marine_response.raw_payload,
                metadata={
                    "application_environment": self._application_environment,
                    "requested_coordinates": [item.model_dump(mode="json") for item in coordinates],
                    "requested_forecast_window": window.model_dump(mode="json"),
                    "requested_variables": {
                        "forecast": list(FORECAST_VARIABLES),
                        "marine": list(MARINE_VARIABLES),
                    },
                    "provider_endpoints": {
                        "forecast": self._client.forecast_base_url,
                        "marine": self._client.marine_base_url,
                    },
                    "cache_status": {
                        "forecast": weather_status.value,
                        "marine": marine_status.value,
                    },
                },
            )

        return RouteWeatherRawResult(
            route_id=route_id,
            requested_at=retrieved_at,
            forecast_window=window,
            points=[
                {
                    "sequence": point.sequence,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                }
                for point in sorted(route.weather_sample_points, key=lambda item: item.sequence)
            ],
            weather_response=weather_response,
            marine_response=marine_response,
            cache_status={"forecast": weather_status, "marine": marine_status},
            snapshot_path=str(snapshot_path) if snapshot_path else None,
        )

    def _get_api_response(
        self,
        *,
        api_type: str,
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        forecast_window: ForecastWindow,
    ) -> tuple[OpenMeteoBatchResponse, WeatherCacheStatus, bool]:
        key = make_weather_cache_key(
            api_type=api_type,
            coordinates=coordinates,
            variables=variables,
            forecast_window=forecast_window,
        )
        entry = self._cache.get(key, now=self._as_utc(self._now()))
        if entry is not None and entry.status == WeatherCacheStatus.HIT:
            response = self._client.validate_cached_response(
                api_type=api_type,
                coordinates=coordinates,
                variables=variables,
                raw_payload=entry.payload,
            )
            return response, WeatherCacheStatus.HIT, False

        try:
            response = self._fetch_batches(
                api_type=api_type,
                coordinates=coordinates,
                variables=variables,
                forecast_window=forecast_window,
            )
        except WeatherProviderError:
            if entry is None:
                raise
            response = self._client.validate_cached_response(
                api_type=api_type,
                coordinates=coordinates,
                variables=variables,
                raw_payload=entry.payload,
            )
            return response, WeatherCacheStatus.STALE, False
        self._cache.set(key, response.raw_payload, created_at=self._as_utc(self._now()))
        status = (
            WeatherCacheStatus.REFRESHED
            if entry is not None
            else WeatherCacheStatus.MISS
        )
        return response, status, True

    def _fetch_batches(
        self,
        *,
        api_type: str,
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        forecast_window: ForecastWindow,
    ) -> OpenMeteoBatchResponse:
        responses: list[OpenMeteoBatchResponse] = []
        for start in range(0, len(coordinates), self._max_coordinates):
            batch = coordinates[start : start + self._max_coordinates]
            if api_type == "forecast":
                response = self._client.get_forecast(
                    batch,
                    forecast_window=forecast_window,
                )
            else:
                response = self._client.get_marine_forecast(
                    batch,
                    forecast_window=forecast_window,
                )
            responses.append(response)
        if len(responses) == 1:
            return responses[0]
        raw_items: list[Any] = []
        for response in responses:
            if isinstance(response.raw_payload, list):
                raw_items.extend(response.raw_payload)
            else:
                raw_items.append(response.raw_payload)
        return self._client.validate_cached_response(
            api_type=api_type,
            coordinates=coordinates,
            variables=variables,
            raw_payload=raw_items,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
