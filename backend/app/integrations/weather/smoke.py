"""Optional live Open-Meteo smoke test for one existing SEA route."""

from __future__ import annotations

import argparse
import json

from ...config import settings
from ...repository import initialise_database, load_runtime_dataset
from .errors import WeatherProviderError
from .runtime import build_weather_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-id", default="ASIA_R_0056")
    args = parser.parse_args()
    if not settings.open_meteo_enabled:
        raise SystemExit(
            "Open-Meteo is disabled. Set OPEN_METEO_ENABLED=true for this optional smoke test."
        )
    initialise_database()
    dataset = load_runtime_dataset()
    service = build_weather_service(dataset.routes, settings)
    try:
        result = service.get_route_weather_raw(args.route_id)
    except WeatherProviderError as exc:
        raise SystemExit(f"Open-Meteo smoke test failed: {exc}") from exc
    finally:
        service.close()
    print(
        json.dumps(
            {
                "route": result.route_id,
                "points_requested": len(result.points),
                "weather_response": "OK",
                "marine_response": "OK",
                "cache": {
                    key: value.value for key, value in result.cache_status.items()
                },
                "snapshot_written": result.snapshot_path,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
