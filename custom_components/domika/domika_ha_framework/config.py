"""Domika homeassistant framework config."""

from dataclasses import dataclass

from aiohttp import ClientTimeout


@dataclass
class Config:
    """Domika homeassistant framework config."""

    database_url: str = ""
    push_server_url: str = ""
    push_server_timeout: ClientTimeout = ClientTimeout(total=10)


CONFIG = Config()
