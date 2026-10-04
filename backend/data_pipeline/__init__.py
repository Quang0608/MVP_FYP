"""Source-neutral interfaces for the canonical data preparation pipeline.

The current MVP does not download or load external data. These modules define
the boundary that future source adapters must implement.
"""

from .validate_data import (
    CanonicalDataset,
    CanonicalDisruptionEvent,
    CanonicalLocation,
    CanonicalPort,
    CanonicalPortMetrics,
    CanonicalRoute,
    CanonicalShipment,
    CanonicalShipmentRouteStep,
    CanonicalVessel,
    CanonicalVesselPosition,
    validate_dataset,
)

__all__ = [
    "CanonicalDataset",
    "CanonicalDisruptionEvent",
    "CanonicalLocation",
    "CanonicalPort",
    "CanonicalPortMetrics",
    "CanonicalRoute",
    "CanonicalShipment",
    "CanonicalShipmentRouteStep",
    "CanonicalVessel",
    "CanonicalVesselPosition",
    "validate_dataset",
]
