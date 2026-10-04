from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.domain import Route, Status, WeatherSamplePoint
from backend.app.integrations.weather.cache import WeatherCache, make_weather_cache_key
from backend.app.integrations.weather.errors import (
    InvalidWeatherRequest,
    InvalidWeatherResponse,
    UnsupportedWeatherRoute,
    WeatherProviderTimeout,
    WeatherProviderUnavailable,
)
from backend.app.integrations.weather.open_meteo_client import (
    FORECAST_VARIABLES,
    MARINE_VARIABLES,
    OpenMeteoClient,
)
from backend.app.integrations.weather.schemas import (
    ForecastWindow,
    WeatherCacheStatus,
    WeatherCoordinate,
)
from backend.app.integrations.weather.service import WeatherService
from backend.app.integrations.weather.snapshots import RawWeatherSnapshotStore


def coordinate_list(count: int = 5) -> list[WeatherCoordinate]:
    return [
        WeatherCoordinate(latitude=1.0 + index, longitude=103.0 + index)
        for index in range(count)
    ]


def provider_payload(
    coordinates: list[WeatherCoordinate], variables: tuple[str, ...]
) -> list[dict[str, object]]:
    hourly = {
        "time": ["2026-09-26T00:00", "2026-09-26T01:00"],
        **{variable: [float(index), float(index + 1)] for index, variable in enumerate(variables)},
    }
    return [
        {
            "latitude": coordinate.latitude,
            "longitude": coordinate.longitude,
            "timezone": "UTC",
            "hourly": hourly,
        }
        for coordinate in coordinates
    ]


def make_route(mode: str = "SEA", samples: int = 5) -> Route:
    return Route(
        route_id="R_TEST_WEATHER",
        source_location_id="P1",
        destination_location_id="P2",
        transport_mode=mode,
        distance_km=1000,
        base_duration_hours=48,
        base_cost=100,
        max_capacity=100,
        risk_score=0.2,
        status=Status.ACTIVE,
        weather_sample_points=[
            WeatherSamplePoint(
                latitude=1.0 + index,
                longitude=103.0 + index,
                sequence=index + 1,
            )
            for index in range(samples)
        ],
    )


def make_client(handler, *, retry_count: int = 0) -> OpenMeteoClient:
    transport = httpx.MockTransport(handler)
    return OpenMeteoClient(
        forecast_base_url="https://forecast.test/v1/forecast",
        marine_base_url="https://marine.test/v1/marine",
        retry_count=retry_count,
        client=httpx.Client(transport=transport),
    )


def test_forecast_and_marine_requests_batch_five_coordinates_and_variables():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = dict(request.url.params)
        coordinates = coordinate_list(len(query["latitude"].split(",")))
        variables = (
            FORECAST_VARIABLES if "forecast" in str(request.url) else MARINE_VARIABLES
        )
        return httpx.Response(200, json=provider_payload(coordinates, variables))

    client = make_client(handler)
    coordinates = coordinate_list()
    forecast = client.get_forecast(coordinates)
    marine = client.get_marine_forecast(coordinates)

    assert len(requests) == 2
    assert requests[0].url.params["latitude"].count(",") == 4
    assert requests[0].url.params["hourly"] == ",".join(FORECAST_VARIABLES)
    assert requests[1].url.params["hourly"] == ",".join(MARINE_VARIABLES)
    assert len(forecast.coordinates) == 5
    assert len(marine.coordinates) == 5
    client.close()


def test_request_window_is_explicit_utc_date_range():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=provider_payload(coordinate_list(1), FORECAST_VARIABLES)[0],
        )

    client = make_client(handler)
    client.get_forecast(
        coordinate_list(1),
        forecast_window=ForecastWindow(
            start_time=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
        ),
    )
    assert captured[0].url.params["timezone"] == "UTC"
    assert captured[0].url.params["start_date"] == "2026-09-28"
    assert captured[0].url.params["end_date"] == "2026-09-30"
    client.close()


def test_missing_requested_variable_is_explicitly_unavailable():
    coordinates = coordinate_list(1)
    payload = provider_payload(coordinates, FORECAST_VARIABLES)[0]
    del payload["hourly"]["visibility"]

    client = make_client(
        lambda request: httpx.Response(200, json=payload)
    )
    response = client.get_forecast(coordinates)
    assert response.missing_variables == {0: ["visibility"]}
    assert "visibility" not in payload["hourly"]
    client.close()


def test_malformed_response_and_array_lengths_are_rejected():
    coordinates = coordinate_list(1)
    payload = provider_payload(coordinates, FORECAST_VARIABLES)[0]
    payload["hourly"]["wind_speed_10m"] = [1.0]
    client = make_client(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(InvalidWeatherResponse):
        client.get_forecast(coordinates)
    client.close()


def test_timeout_retries_are_bounded():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout")

    client = make_client(handler, retry_count=2)
    with pytest.raises(WeatherProviderTimeout):
        client.get_forecast(coordinate_list(1))
    assert attempts == 3
    client.close()


def test_temporary_5xx_retries_but_4xx_does_not():
    attempts = 0

    def temporary_failure(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    client = make_client(temporary_failure, retry_count=2)
    with pytest.raises(WeatherProviderUnavailable):
        client.get_forecast(coordinate_list(1))
    assert attempts == 3
    client.close()

    attempts = 0

    def invalid_request(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"error": True})

    client = make_client(invalid_request, retry_count=2)
    with pytest.raises(InvalidWeatherRequest):
        client.get_forecast(coordinate_list(1))
    assert attempts == 1
    client.close()


def test_cache_key_distinguishes_coordinates_variables_and_window(tmp_path):
    coordinates = coordinate_list()
    first = make_weather_cache_key(
        api_type="forecast",
        coordinates=coordinates,
        variables=FORECAST_VARIABLES,
        forecast_window=ForecastWindow(),
    )
    second = make_weather_cache_key(
        api_type="marine",
        coordinates=coordinates,
        variables=MARINE_VARIABLES,
        forecast_window=ForecastWindow(
            start_time=datetime(2026, 9, 26, tzinfo=timezone.utc)
        ),
    )
    assert first != second

    cache = WeatherCache(tmp_path, ttl_minutes=30)
    cache.set(first, {"hourly": {"time": []}}, created_at=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert cache.get(first, now=datetime(2026, 9, 26, 0, 10, tzinfo=timezone.utc)).status == WeatherCacheStatus.HIT
    assert cache.get(first, now=datetime(2026, 9, 26, 1, tzinfo=timezone.utc)).status == WeatherCacheStatus.STALE


def test_snapshot_store_writes_immutable_distinct_snapshots(tmp_path):
    store = RawWeatherSnapshotStore(tmp_path)
    retrieved = datetime(2026, 9, 26, tzinfo=timezone.utc)
    first = store.save(
        route_id="R_TEST_WEATHER",
        retrieved_at=retrieved,
        forecast_payload={"forecast": 1},
        marine_payload={"marine": 1},
        metadata={"requested_coordinates": []},
        request_id="one",
    )
    second = store.save(
        route_id="R_TEST_WEATHER",
        retrieved_at=retrieved,
        forecast_payload={"forecast": 2},
        marine_payload={"marine": 2},
        metadata={"requested_coordinates": []},
        request_id="two",
    )
    assert first != second
    assert json.loads((first / "forecast.json").read_text()) == {"forecast": 1}
    assert json.loads((second / "forecast.json").read_text()) == {"forecast": 2}
    assert json.loads((first / "metadata.json").read_text())["request_id"] == "one"


def test_route_service_batches_five_points_and_reuses_cache(tmp_path):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        query = dict(request.url.params)
        coordinates = coordinate_list(len(query["latitude"].split(",")))
        variables = FORECAST_VARIABLES if "forecast" in str(request.url) else MARINE_VARIABLES
        return httpx.Response(200, json=provider_payload(coordinates, variables))

    client = make_client(handler)
    service = WeatherService(
        routes=[make_route()],
        client=client,
        cache=WeatherCache(tmp_path / "cache", ttl_minutes=30),
        snapshots=RawWeatherSnapshotStore(tmp_path / "raw"),
        now_fn=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc),
    )
    first = service.get_route_weather_raw("R_TEST_WEATHER")
    second = service.get_route_weather_raw("R_TEST_WEATHER")

    assert len(calls) == 2
    assert len(first.points) == 5
    assert first.cache_status == {
        "forecast": WeatherCacheStatus.MISS,
        "marine": WeatherCacheStatus.MISS,
    }
    assert second.cache_status == {
        "forecast": WeatherCacheStatus.HIT,
        "marine": WeatherCacheStatus.HIT,
    }
    assert first.snapshot_path is not None
    assert second.snapshot_path is None
    client.close()


def test_stale_cache_fallback_is_explicit(tmp_path):
    now = [datetime(2026, 9, 26, tzinfo=timezone.utc)]
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            query = dict(request.url.params)
            coordinates = coordinate_list(len(query["latitude"].split(",")))
            variables = FORECAST_VARIABLES if "forecast" in str(request.url) else MARINE_VARIABLES
            return httpx.Response(200, json=provider_payload(coordinates, variables))
        raise httpx.ReadTimeout("provider unavailable")

    client = make_client(handler, retry_count=0)
    service = WeatherService(
        routes=[make_route()],
        client=client,
        cache=WeatherCache(tmp_path / "cache", ttl_minutes=1),
        snapshots=RawWeatherSnapshotStore(tmp_path / "raw"),
        now_fn=lambda: now[0],
    )
    service.get_route_weather_raw("R_TEST_WEATHER")
    now[0] = now[0] + timedelta(minutes=2)
    stale = service.get_route_weather_raw("R_TEST_WEATHER")
    assert stale.cache_status == {
        "forecast": WeatherCacheStatus.STALE,
        "marine": WeatherCacheStatus.STALE,
    }
    assert attempts == 4
    client.close()


def test_non_sea_and_missing_sample_routes_are_rejected(tmp_path):
    road = make_route("ROAD")
    missing = make_route("SEA", samples=0)
    missing.route_id = "R_TEST_WEATHER_MISSING"
    client = make_client(lambda request: httpx.Response(500))
    service = WeatherService(
        routes=[road, missing],
        client=client,
        cache=WeatherCache(tmp_path / "cache", ttl_minutes=30),
        snapshots=RawWeatherSnapshotStore(tmp_path / "raw"),
    )
    with pytest.raises(UnsupportedWeatherRoute):
        service.get_route_weather_raw("R_TEST_WEATHER")
    with pytest.raises(UnsupportedWeatherRoute):
        service.get_route_weather_raw("R_TEST_WEATHER_MISSING")
    client.close()
