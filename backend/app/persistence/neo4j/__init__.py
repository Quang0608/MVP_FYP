"""Opt-in Neo4j foundation for the staged persistence migration."""

from .driver import (
    Neo4jConfigurationError,
    Neo4jConnectionError,
    Neo4jConnectionManager,
    Neo4jHealth,
    managed_neo4j_connection,
)
from .schema import bootstrap_schema

__all__ = [
    "Neo4jConfigurationError",
    "Neo4jConnectionError",
    "Neo4jConnectionManager",
    "Neo4jHealth",
    "bootstrap_schema",
    "managed_neo4j_connection",
]
