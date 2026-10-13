"""Opt-in Neo4j foundation for the staged persistence migration."""

from .driver import (
    Neo4jConfigurationError,
    Neo4jConnectionError,
    Neo4jConnectionManager,
    Neo4jHealth,
    managed_neo4j_connection,
)
from .schema import bootstrap_schema
from .impact import (
    DownstreamLegEvidence,
    GraphPathStep,
    KGImpactEvidence,
    KGImpactResult,
    Neo4jImpactQueryError,
    Neo4jImpactQueryService,
)
from .write_repository import (
    Neo4jUnsupportedWriteError,
    Neo4jWriteConflictError,
    Neo4jWriteError,
    Neo4jWriteNotFoundError,
    Neo4jWriteRepository,
    Neo4jWriteValidationError,
    WriteReceipt,
)

__all__ = [
    "Neo4jConfigurationError",
    "Neo4jConnectionError",
    "Neo4jConnectionManager",
    "Neo4jHealth",
    "bootstrap_schema",
    "managed_neo4j_connection",
    "DownstreamLegEvidence",
    "GraphPathStep",
    "KGImpactEvidence",
    "KGImpactResult",
    "Neo4jImpactQueryError",
    "Neo4jImpactQueryService",
    "Neo4jUnsupportedWriteError",
    "Neo4jWriteConflictError",
    "Neo4jWriteError",
    "Neo4jWriteNotFoundError",
    "Neo4jWriteRepository",
    "Neo4jWriteValidationError",
    "WriteReceipt",
]
