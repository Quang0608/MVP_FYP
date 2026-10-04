"""Disruption-event normalization interface."""

from collections.abc import Iterable, Mapping
from typing import Any

from .validate_data import CanonicalDisruptionEvent


def normalize_disruptions(
    source_rows: Iterable[Mapping[str, Any]],
    source_mappings: Mapping[str, str],
) -> list[CanonicalDisruptionEvent]:
    """Normalize weather, news, port, and manual events into one contract."""

    raise NotImplementedError(
        "Disruption normalization is not implemented; event classification and confidence need review."
    )
