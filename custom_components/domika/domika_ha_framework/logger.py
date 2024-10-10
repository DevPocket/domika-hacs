"""Domika homeassistant framework logger."""

import logging

logger = logging.getLogger("domika_ha_framework")
logger.addHandler(logging.NullHandler())
