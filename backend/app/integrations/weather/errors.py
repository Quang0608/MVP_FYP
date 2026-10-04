"""Typed failures at the weather provider boundary."""

from __future__ import annotations


class WeatherProviderError(RuntimeError):
    """Base error that callers can handle without knowing httpx details."""

    retryable = False

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidWeatherRequest(WeatherProviderError):
    pass


class WeatherProviderTimeout(WeatherProviderError):
    retryable = True


class WeatherProviderUnavailable(WeatherProviderError):
    retryable = True


class WeatherRateLimited(WeatherProviderError):
    pass


class InvalidWeatherResponse(WeatherProviderError):
    pass


class UnsupportedWeatherRoute(WeatherProviderError):
    pass


class WeatherCacheError(WeatherProviderError):
    pass


class SnapshotPersistenceError(WeatherProviderError):
    pass
