"""Application adapters for normalized external data."""

from .canonical import load_port_master_locations, locations_from_port_master

__all__ = ["load_port_master_locations", "locations_from_port_master"]
