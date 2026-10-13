from typing import Literal

from pydantic import SecretStr, field_validator
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
    persistence_backend: Literal["sqlite", "neo4j"] = "sqlite"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"
    neo4j_snapshot_id: str = "asia-runtime-seed-20260913"
    neo4j_import_scope: str = "phase2-active-asia-snapshot"
    neo4j_write_snapshot_id: str = "neo4j-runtime-write-v1"
    neo4j_write_import_scope: str = "neo4j-runtime-write-v1"
    neo4j_connection_timeout_seconds: float = 10
    neo4j_connection_acquisition_timeout_seconds: float = 10
    neo4j_max_transaction_retry_time_seconds: float = 10

    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri(cls, value: str) -> str:
        allowed_schemes = (
            "bolt://",
            "bolt+ssc://",
            "bolt+s://",
            "neo4j://",
            "neo4j+ssc://",
            "neo4j+s://",
        )
        if not value.startswith(allowed_schemes):
            raise ValueError("neo4j_uri must use a supported Neo4j URI scheme")
        return value

    @field_validator(
        "neo4j_connection_timeout_seconds",
        "neo4j_connection_acquisition_timeout_seconds",
        "neo4j_max_transaction_retry_time_seconds",
    )
    @classmethod
    def validate_neo4j_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Neo4j timeout values must be greater than zero")
        return value

    @field_validator(
        "neo4j_snapshot_id",
        "neo4j_import_scope",
        "neo4j_write_snapshot_id",
        "neo4j_write_import_scope",
    )
    @classmethod
    def validate_neo4j_scope_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Neo4j snapshot and scope values must not be empty")
        return value.strip()


settings = Settings()
