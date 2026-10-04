"""HTTP-only Open-Meteo Forecast and Marine API adapter."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import httpx

from .errors import (
    InvalidWeatherRequest,
    InvalidWeatherResponse,
    WeatherProviderError,
    WeatherProviderTimeout,
    WeatherProviderUnavailable,
    WeatherRateLimited,
)
from .schemas import (
    ForecastWindow,
    OpenMeteoBatchResponse,
    WeatherCoordinate,
)

FORECAST_VARIABLES = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "precipitation",
    "visibility",
    "weather_code",
)
MARINE_VARIABLES = (
    "wave_height",
    "wave_period",
    "swell_wave_height",
    "swell_wave_period",
    "ocean_current_velocity",
)


class OpenMeteoClient:
    """Retrieve and validate raw provider payloads without business decisions."""

    def __init__(
        self,
        *,
        forecast_base_url: str = "https://api.open-meteo.com/v1/forecast",
        marine_base_url: str = "https://marine-api.open-meteo.com/v1/marine",
        timeout_seconds: float = 20,
        retry_count: int = 2,
        client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Weather provider timeout must be positive")
        if retry_count < 0:
            raise ValueError("Weather provider retry_count must not be negative")
        self.forecast_base_url = forecast_base_url
        self.marine_base_url = marine_base_url
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._sleep = sleep_fn or (lambda _: None)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenMeteoClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_forecast(
        self,
        coordinates: list[WeatherCoordinate],
        *,
        forecast_window: ForecastWindow | None = None,
    ) -> OpenMeteoBatchResponse:
        return self._get(
            api_type="forecast",
            endpoint=self.forecast_base_url,
            coordinates=coordinates,
            variables=FORECAST_VARIABLES,
            forecast_window=forecast_window or ForecastWindow(),
        )

    def get_marine_forecast(
        self,
        coordinates: list[WeatherCoordinate],
        *,
        forecast_window: ForecastWindow | None = None,
    ) -> OpenMeteoBatchResponse:
        return self._get(
            api_type="marine",
            endpoint=self.marine_base_url,
            coordinates=coordinates,
            variables=MARINE_VARIABLES,
            forecast_window=forecast_window or ForecastWindow(),
        )

    def validate_cached_response(
        self,
        *,
        api_type: str,
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        raw_payload: dict[str, Any] | list[Any],
    ) -> OpenMeteoBatchResponse:
        return self._validated_response(
            api_type=api_type,
            coordinates=coordinates,
            variables=variables,
            raw_payload=raw_payload,
        )

    def _get(
        self,
        *,
        api_type: str,
        endpoint: str,
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        forecast_window: ForecastWindow,
    ) -> OpenMeteoBatchResponse:
        self._validate_coordinates(coordinates)
        params = self._request_params(coordinates, variables, forecast_window)
        response = self._request_with_retries(endpoint, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidWeatherResponse(
                f"Open-Meteo {api_type} response was not valid JSON"
            ) from exc
        if not isinstance(payload, (dict, list)):
            raise InvalidWeatherResponse(
                f"Open-Meteo {api_type} response must be an object or list"
            )
        if isinstance(payload, dict) and payload.get("error"):
            reason = payload.get("reason", "provider rejected the request")
            raise InvalidWeatherRequest(f"Open-Meteo rejected {api_type} request: {reason}")
        return self._validated_response(
            api_type=api_type,
            coordinates=coordinates,
            variables=variables,
            raw_payload=payload,
        )

    def _request_with_retries(
        self,
        endpoint: str,
        params: dict[str, str],
    ) -> httpx.Response:
        for attempt in range(self.retry_count + 1):
            try:
                response = self._client.get(endpoint, params=params)
            except httpx.TimeoutException as exc:
                if attempt < self.retry_count:
                    self._sleep(0)
                    continue
                raise WeatherProviderTimeout("Open-Meteo request timed out") from exc
            except httpx.RequestError as exc:
                if attempt < self.retry_count:
                    self._sleep(0)
                    continue
                raise WeatherProviderUnavailable(
                    "Open-Meteo request could not reach the provider"
                ) from exc
            if response.status_code == 429:
                raise WeatherRateLimited(
                    "Open-Meteo rate-limited the request", status_code=response.status_code
                )
            if 500 <= response.status_code <= 599:
                if attempt < self.retry_count:
                    self._sleep(0)
                    continue
                raise WeatherProviderUnavailable(
                    f"Open-Meteo returned provider error {response.status_code}",
                    status_code=response.status_code,
                )
            if 400 <= response.status_code <= 499:
                raise InvalidWeatherRequest(
                    f"Open-Meteo rejected the request with HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise WeatherProviderUnavailable(
                    "Open-Meteo returned an unexpected HTTP status",
                    status_code=response.status_code,
                ) from exc
            return response
        raise WeatherProviderError("Open-Meteo request did not produce a response")

    @staticmethod
    def _validate_coordinates(coordinates: list[WeatherCoordinate]) -> None:
        if not coordinates:
            raise InvalidWeatherRequest("At least one weather coordinate is required")
        for coordinate in coordinates:
            if not (-90 <= coordinate.latitude <= 90):
                raise InvalidWeatherRequest("Weather latitude is outside -90..90")
            if not (-180 <= coordinate.longitude <= 180):
                raise InvalidWeatherRequest("Weather longitude is outside -180..180")

    @staticmethod
    def _request_params(
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        forecast_window: ForecastWindow,
    ) -> dict[str, str]:
        params = {
            "latitude": ",".join(str(coordinate.latitude) for coordinate in coordinates),
            "longitude": ",".join(str(coordinate.longitude) for coordinate in coordinates),
            "hourly": ",".join(variables),
            "timezone": "UTC",
            "timeformat": "iso8601",
        }
        params.update(forecast_window.as_request_dates())
        return params

    @classmethod
    def _validated_response(
        cls,
        *,
        api_type: str,
        coordinates: list[WeatherCoordinate],
        variables: tuple[str, ...],
        raw_payload: dict[str, Any] | list[Any],
    ) -> OpenMeteoBatchResponse:
        response_items: list[Any]
        if isinstance(raw_payload, list):
            response_items = raw_payload
        else:
            response_items = [raw_payload]
        if len(response_items) != len(coordinates):
            raise InvalidWeatherResponse(
                f"Open-Meteo {api_type} response returned {len(response_items)} "
                f"locations for {len(coordinates)} requested coordinates"
            )
        missing_variables: dict[int, list[str]] = {}
        for index, item in enumerate(response_items):
            if not isinstance(item, dict):
                raise InvalidWeatherResponse(
                    f"Open-Meteo {api_type} location {index} was not an object"
                )
            cls._validate_location_metadata(item, api_type, index)
            hourly = item.get("hourly")
            if not isinstance(hourly, dict):
                raise InvalidWeatherResponse(
                    f"Open-Meteo {api_type} location {index} has no hourly object"
                )
            times = hourly.get("time")
            if not isinstance(times, list) or not times or not all(
                isinstance(value, str) and value for value in times
            ):
                raise InvalidWeatherResponse(
                    f"Open-Meteo {api_type} location {index} has invalid hourly time data"
                )
            missing = []
            for variable in variables:
                values = hourly.get(variable)
                if values is None:
                    missing.append(variable)
                    continue
                if not isinstance(values, list) or len(values) != len(times):
                    raise InvalidWeatherResponse(
                        f"Open-Meteo {api_type} variable {variable} has inconsistent length"
                    )
                for value in values:
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                    ):
                        raise InvalidWeatherResponse(
                            f"Open-Meteo {api_type} variable {variable} contains malformed data"
                        )
            if missing:
                missing_variables[index] = missing
        return OpenMeteoBatchResponse(
            api_type=api_type,
            coordinates=coordinates,
            requested_variables=variables,
            raw_payload=raw_payload,
            missing_variables=missing_variables,
        )

    @staticmethod
    def _validate_location_metadata(
        item: dict[str, Any], api_type: str, index: int
    ) -> None:
        for name, lower, upper in (
            ("latitude", -90, 90),
            ("longitude", -180, 180),
        ):
            value = item.get(name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not lower <= float(value) <= upper
            ):
                raise InvalidWeatherResponse(
                    f"Open-Meteo {api_type} location {index} has invalid {name}"
                )
