"""Provider-independent external-signal and network-exposure contracts."""

from .corridors import NETWORK_ZONES, NetworkZone, NetworkZoneType, get_network_zones
from .schemas import (
    ExternalExposureResult,
    ExternalSignal,
    NetworkMatchType,
    OperationalEffect,
    ShipmentExposure,
    ShipmentTraversalWindow,
    SignalNetworkMatch,
)
from .service import find_shipments_exposed

__all__ = [
    "ExternalExposureResult",
    "ExternalSignal",
    "NETWORK_ZONES",
    "NetworkMatchType",
    "NetworkZone",
    "NetworkZoneType",
    "OperationalEffect",
    "ShipmentExposure",
    "ShipmentTraversalWindow",
    "SignalNetworkMatch",
    "find_shipments_exposed",
    "get_network_zones",
]
