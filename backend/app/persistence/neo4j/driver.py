"""Lifecycle-managed Neo4j driver access for the foundation phase."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Mapping

from neo4j import GraphDatabase

from ...config import Settings, settings


class Neo4jConfigurationError(ValueError):
    """Raised when required Neo4j configuration is missing or invalid."""


class Neo4jConnectionError(ConnectionError):
    """Raised when Neo4j connectivity verification fails."""


@dataclass(frozen=True)
class Neo4jHealth:
    """Sanitized health result that never contains connection credentials."""

    status: str
    database: str
    detail: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


class Neo4jConnectionManager:
    """Own one driver and scope all sessions to the configured database."""

    def __init__(self, configuration: Settings) -> None:
        self.configuration = configuration
        self._driver: Any | None = None

    @property
    def is_started(self) -> bool:
        return self._driver is not None

    def start(self) -> None:
        """Create one driver and verify connectivity before exposing it."""

        if self._driver is not None:
            return
        password = self.configuration.neo4j_password.get_secret_value()
        if not password:
            raise Neo4jConfigurationError(
                "NEO4J_PASSWORD is required when using the Neo4j foundation"
            )
        driver = None
        try:
            driver = GraphDatabase.driver(
                self.configuration.neo4j_uri,
                auth=(self.configuration.neo4j_username, password),
                connection_timeout=self.configuration.neo4j_connection_timeout_seconds,
                connection_acquisition_timeout=(
                    self.configuration.neo4j_connection_acquisition_timeout_seconds
                ),
                max_transaction_retry_time=(
                    self.configuration.neo4j_max_transaction_retry_time_seconds
                ),
            )
            driver.verify_connectivity()
        except Exception as exc:
            if driver is not None:
                driver.close()
            raise Neo4jConnectionError(
                "Neo4j connectivity verification failed"
            ) from exc
        self._driver = driver

    def close(self) -> None:
        """Close the owned driver; repeated calls are safe."""

        if self._driver is None:
            return
        self._driver.close()
        self._driver = None

    @contextmanager
    def session(self) -> Iterator[Any]:
        """Yield one explicit-database session and always close it."""

        if self._driver is None:
            self.start()
        session = self._driver.session(database=self.configuration.neo4j_database)
        try:
            yield session
        finally:
            session.close()

    def verify_connectivity(self) -> None:
        """Verify the active driver without exposing the underlying error."""

        if self._driver is None:
            self.start()
            return
        try:
            self._driver.verify_connectivity()
        except Exception as exc:
            raise Neo4jConnectionError(
                "Neo4j connectivity verification failed"
            ) from exc

    def health_check(self) -> Neo4jHealth:
        """Return a sanitized health result for CLI or future app wiring."""

        try:
            self.verify_connectivity()
            self.execute_read("RETURN 1 AS ok")
        except Neo4jConfigurationError:
            return Neo4jHealth(
                status="unconfigured",
                database=self.configuration.neo4j_database,
                detail="NEO4J_PASSWORD is not configured",
            )
        except Neo4jConnectionError:
            return Neo4jHealth(
                status="unavailable",
                database=self.configuration.neo4j_database,
                detail="Neo4j connectivity verification failed",
            )
        return Neo4jHealth(status="ok", database=self.configuration.neo4j_database)

    def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run an allowlisted caller query through a managed read transaction."""

        with self.session() as session:
            return session.execute_read(
                lambda transaction: (
                    transaction.run(
                        query,
                        parameters or {},
                        **(
                            {"timeout": timeout_seconds}
                            if timeout_seconds is not None
                            else {}
                        ),
                    ).data()
                )
            )

    def execute_write(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a schema/bootstrap query through a managed write transaction."""

        with self.session() as session:
            return session.execute_write(
                lambda transaction: transaction.run(
                    query,
                    parameters or {},
                ).data()
            )


@contextmanager
def managed_neo4j_connection(
    configuration: Settings = settings,
) -> Iterator[Neo4jConnectionManager]:
    """Start, yield, and close one manager for a bounded application lifespan."""

    manager = Neo4jConnectionManager(configuration)
    manager.start()
    try:
        yield manager
    finally:
        manager.close()
