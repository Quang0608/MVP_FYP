"""Location normalization interface."""

from collections.abc import Iterable, Mapping
from typing import Any

from .validate_data import CanonicalLocation


def normalize_locations(
    source_rows: Iterable[Mapping[str, Any]],
    source_mappings: Mapping[str, str],
) -> list[CanonicalLocation]:
    """Resolve source rows into canonical locations."""

    raise NotImplementedError(
        "Location normalization is not implemented; resolve source IDs through mappings first."
    )
