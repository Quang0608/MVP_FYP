"""Provider-isolated raw weather retrieval integrations."""

from .cache import WeatherCache, make_weather_cache_key
from .errors import (
    InvalidWeatherRequest,
    InvalidWeatherResponse,
    SnapshotPersistenceError,
    UnsupportedWeatherRoute,
    WeatherCacheError,
    WeatherProviderError,
    WeatherProviderTimeout,
    WeatherProviderUnavailable,
    WeatherRateLimited,
)
from .open_meteo_client import OpenMeteoClient
from .schemas import (
    ForecastWindow,
    OpenMeteoBatchResponse,
    RouteWeatherRawResult,
    WeatherCoordinate,
)
from .service import WeatherService
from .snapshots import RawWeatherSnapshotStore

__all__ = [
    "ForecastWindow",
    "InvalidWeatherRequest",
    "InvalidWeatherResponse",
    "OpenMeteoBatchResponse",
    "OpenMeteoClient",
    "RawWeatherSnapshotStore",
    "RouteWeatherRawResult",
    "SnapshotPersistenceError",
    "UnsupportedWeatherRoute",
    "WeatherCache",
    "WeatherCacheError",
    "WeatherCoordinate",
    "WeatherProviderError",
    "WeatherProviderTimeout",
    "WeatherProviderUnavailable",
    "WeatherRateLimited",
    "WeatherService",
    "make_weather_cache_key",
]
