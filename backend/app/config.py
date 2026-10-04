from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite:///./reroute_agent.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 60
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8501,http://127.0.0.1:8501"
    )
    portwatch_enabled: bool = True
    portwatch_state_path: str = "data/processed/portwatch/current_port_state.parquet"
    portwatch_disruptions_path: str = "data/processed/portwatch/current_disruptions.parquet"
    portwatch_affected_ports_path: str = "data/processed/portwatch/disruption_affected_ports.parquet"
    runtime_location_mapping_path: str = "data/mappings/runtime_location_mapping.csv"
    open_meteo_enabled: bool = False
    open_meteo_forecast_base_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_marine_base_url: str = "https://marine-api.open-meteo.com/v1/marine"
    open_meteo_request_timeout_seconds: float = 20
    open_meteo_retry_count: int = 2
    open_meteo_cache_ttl_minutes: int = 30
    open_meteo_raw_snapshot_directory: str = "data/raw/weather/open_meteo"
    open_meteo_cache_directory: str = "data/cache/weather/open_meteo"
    open_meteo_max_coordinates_per_request: int = 50


settings = Settings()
