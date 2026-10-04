"""Route normalization interface."""

from collections.abc import Iterable, Mapping
from typing import Any

from .validate_data import CanonicalRoute


def normalize_routes(
    source_rows: Iterable[Mapping[str, Any]],
    source_mappings: Mapping[str, str],
) -> list[CanonicalRoute]:
    """Resolve source geometry or transport rows into canonical routes."""

    raise NotImplementedError(
        "Route normalization is not implemented; keep route construction source-neutral."
    )
