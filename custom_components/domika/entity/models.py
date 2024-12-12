"""Domika entity models."""

from dataclasses import dataclass


@dataclass
class DomikaEntitiesList():
    """Entities data: name, related ids and capabilities."""
    entities: dict


@dataclass
class DomikaEntityInfo():
    """Entity data: name, related ids and capabilities."""
    info: dict
