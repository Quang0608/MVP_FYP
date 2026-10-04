"""Port activity normalization interface."""

from collections.abc import Iterable, Mapping
from typing import Any

from .validate_data import CanonicalPortMetrics


def normalize_port_metrics(
    source_rows: Iterable[Mapping[str, Any]],
    source_mappings: Mapping[str, str],
) -> list[CanonicalPortMetrics]:
    """Resolve PortWatch-style rows into canonical port metrics."""

    raise NotImplementedError(
        "Port metric normalization is not implemented; map provider ports first."
    )
