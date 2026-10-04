"""Vessel and AIS identity normalization interface."""

from collections.abc import Iterable, Mapping
from typing import Any

from .validate_data import CanonicalVessel, CanonicalVesselPosition


def normalize_vessels(
    source_rows: Iterable[Mapping[str, Any]],
) -> tuple[list[CanonicalVessel], list[CanonicalVesselPosition]]:
    """Resolve vessel master and position rows using the MMSI identity."""

    raise NotImplementedError(
        "Vessel normalization is not implemented; confirm MMSI identity rules first."
    )
