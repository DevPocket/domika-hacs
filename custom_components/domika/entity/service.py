"""Domika entity service."""

from typing import cast

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.light import (
    ColorMode,
    LightEntityFeature,
    get_supported_color_modes,
)
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.search import ItemType, Searcher
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, Platform, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    device_registry as dr,
    entity as hass_entity,
    entity_registry as er,
)
from homeassistant.helpers.entity_registry import RegistryEntry

from ..domika_logger import LOGGER
from .models import DomikaEntitiesList, DomikaEntityInfo


def _related(hass: HomeAssistant, root_entity_id: str) -> set[str]:
    LOGGER.finest("Entity.service._related called, root_entity_id: %s", root_entity_id)

    searcher = Searcher(hass, hass_entity.entity_sources(hass))
    related_devices = searcher.async_search(ItemType.ENTITY, root_entity_id)
    res = set()
    if related_devices and "device" in related_devices:
        related_device_id = related_devices["device"].pop()
        related_entities = searcher.async_search(ItemType.DEVICE, related_device_id)
        if related_entities and "entity" in related_entities:
            res = related_entities["entity"]

    LOGGER.finest("Entity.service._related called, res: %s", res)
    return res


def _capabilities_light(hass: HomeAssistant, entity_id: str) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_light called, entity_id: %s", entity_id)

    capabilities = set()
    supported_modes = get_supported_color_modes(hass, entity_id) or set()
    supported_features = hass_entity.get_supported_features(hass, entity_id)
    if ColorMode.COLOR_TEMP in supported_modes:
        capabilities.add("brightness")
        capabilities.add("colorTemperature")
    if ColorMode.BRIGHTNESS in supported_modes:
        capabilities.add("brightness")
    if (
        (ColorMode.RGB in supported_modes)
        or (ColorMode.HS in supported_modes)
        or (ColorMode.RGBW in supported_modes)
        or (ColorMode.RGBWW in supported_modes)
        or (ColorMode.XY in supported_modes)
    ):
        capabilities.add("brightness")
        capabilities.add("color")

    if supported_features & LightEntityFeature.EFFECT:
        capabilities.add("effect")

    LOGGER.finest(
        "Entity.service._capabilities_light, entity_id: %s, supported_features: %s, supported_modes: %s, "
        "capabilities: %s",
        entity_id,
        supported_features,
        supported_modes,
        capabilities
    )

    return capabilities


def _capabilities_climate(hass: HomeAssistant, entity_id: str) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_climate called, entity_id: %s", entity_id)

    capabilities = set()
    supported_features = hass_entity.get_supported_features(hass, entity_id)
    if supported_features & ClimateEntityFeature.TARGET_TEMPERATURE:
        capabilities.add("temperature")
    if supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
        capabilities.add("temperatureRange")
    if supported_features & ClimateEntityFeature.TARGET_HUMIDITY:
        capabilities.add("humidity")
    if supported_features & ClimateEntityFeature.FAN_MODE:
        capabilities.add("fan")
    if supported_features & ClimateEntityFeature.PRESET_MODE:
        capabilities.add("preset")

    LOGGER.finest(
        "Entity.service._capabilities_climate, entity_id: %s, supported_features: %s, capabilities: %s",
        entity_id,
        supported_features,
        capabilities
    )
    return capabilities


def _capabilities_player(hass: HomeAssistant, entity_id: str) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_player called, entity_id: %s", entity_id)
    capabilities = set()
    supported_features = hass_entity.get_supported_features(hass, entity_id)
    if supported_features & MediaPlayerEntityFeature.PLAY:
        capabilities.add("play")
    if supported_features & MediaPlayerEntityFeature.PAUSE:
        capabilities.add("pause")
    if supported_features & MediaPlayerEntityFeature.VOLUME_SET:
        capabilities.add("setVolume")
    if supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
        capabilities.add("selectSource")
    LOGGER.finest(
        "Entity.service._capabilities_player, entity_id: %s, supported_features: %s, capabilities: %s",
        entity_id,
        supported_features,
        capabilities
    )
    return capabilities


def _capabilities_lock(entity_id: str, device_class: str) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_lock called, entity_id: %s", entity_id)
    capabilities = set()
    if BinarySensorDeviceClass.DOOR == device_class:
        capabilities.add(BinarySensorDeviceClass.DOOR)
    elif BinarySensorDeviceClass.GARAGE_DOOR in device_class:
        capabilities.add(BinarySensorDeviceClass.GARAGE_DOOR)
    elif BinarySensorDeviceClass.WINDOW in device_class:
        capabilities.add(BinarySensorDeviceClass.WINDOW)
    LOGGER.finest(
        "Entity.service._capabilities_lock, entity_id: %s, capabilities: %s",
        entity_id,
        capabilities
    )
    return capabilities


def _capabilities_cover(hass: HomeAssistant, entity_id: str) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_cover called, entity_id: %s", entity_id)
    capabilities = set()
    # CoverEntityFeature
    supported_features = hass_entity.get_supported_features(hass, entity_id)
    if supported_features & CoverEntityFeature.OPEN:
        capabilities.add("open")
    if supported_features & CoverEntityFeature.CLOSE:
        capabilities.add("close")
    if supported_features & CoverEntityFeature.STOP:
        capabilities.add("stop")
    if supported_features & CoverEntityFeature.SET_POSITION:
        capabilities.add("setPosition")
    if supported_features & CoverEntityFeature.OPEN_TILT:
        capabilities.add("openTilt")
    if supported_features & CoverEntityFeature.CLOSE_TILT:
        capabilities.add("closeTilt")
    if supported_features & CoverEntityFeature.STOP_TILT:
        capabilities.add("stopTilt")
    if supported_features & CoverEntityFeature.SET_TILT_POSITION:
        capabilities.add("setTiltPosition")
    LOGGER.finest(
        "Entity.service._capabilities_cover, entity_id: %s, supported_features: %s, capabilities: %s",
        entity_id,
        supported_features,
        capabilities
    )
    return capabilities


def _capabilities_sensor(_hass: HomeAssistant, state: State) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_sensor called, state: %s", state)
    capabilities = set()
    if state.attributes.get(ATTR_DEVICE_CLASS):
        capabilities.add(cast(str, state.attributes.get(ATTR_DEVICE_CLASS)))
    else:
        capabilities.add(cast(str, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)))
    LOGGER.finest(
        "Entity.service._capabilities_cover, state: %s, capabilities: %s",
        state,
        capabilities
    )
    return capabilities


def _capabilities_binary_sensor(_hass: HomeAssistant, state: State) -> set[str]:
    LOGGER.finest("Entity.service._capabilities_binary_sensor called, state: %s", state)
    capabilities = set()
    if state.attributes.get(ATTR_DEVICE_CLASS):
        capabilities.add(cast(str, state.attributes.get(ATTR_DEVICE_CLASS)))
    else:
        capabilities.add(cast(str, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)))
    LOGGER.finest(
        "Entity.service._capabilities_binary_sensor, state: %s, capabilities: %s",
        state,
        capabilities
    )
    return capabilities


def _related_climate(hass: HomeAssistant, entity_id: str) -> dict:
    LOGGER.finest("Entity.service._related_climate called, entity_id: %s", entity_id)
    related_ids = {}
    for related_id in _related(hass, entity_id):
        state = hass.states.get(related_id)
        if not state:
            continue
        if (
            (state.domain in ["sensor"])
            and (ATTR_DEVICE_CLASS in state.attributes)
            and (
                state.attributes[ATTR_DEVICE_CLASS]
                in [
                    SensorDeviceClass.TEMPERATURE,
                    SensorDeviceClass.HUMIDITY,
                ]
            )
        ):
            related_ids[state.attributes[ATTR_DEVICE_CLASS]] = related_id
    LOGGER.finest(
        "Entity.service._capabilities_binary_sensor, entity_id: %s, related_ids: %s",
        entity_id,
        related_ids
    )
    return related_ids


def _related_lock(hass: HomeAssistant, entity_id: str) -> dict:
    LOGGER.finest("Entity.service._related_lock called, entity_id: %s", entity_id)
    related_ids = {}
    for related_id in _related(hass, entity_id):
        state = hass.states.get(related_id)
        if not state:
            continue
        if (
            (state.domain in ["binary_sensor"])
            and (ATTR_DEVICE_CLASS in state.attributes)
            and (
                state.attributes[ATTR_DEVICE_CLASS]
                in [
                    BinarySensorDeviceClass.DOOR,
                    BinarySensorDeviceClass.GARAGE_DOOR,
                    BinarySensorDeviceClass.WINDOW,
                ]
            )
        ):
            related_ids[state.attributes[ATTR_DEVICE_CLASS]] = related_id
    LOGGER.finest(
        "Entity.service._related_lock, entity_id: %s, related_ids: %s",
        entity_id,
        related_ids
    )
    return related_ids


def _related_area(hass: HomeAssistant, entity_id: str) -> str:
    LOGGER.finest("Entity.service._related_area called, entity_id: %s", entity_id)
    res = ""
    if entity_entry := er.async_get(hass).async_get(entity_id):
        if entity_entry.area_id:
            res = entity_entry.area_id

        searcher = Searcher(hass, hass_entity.entity_sources(hass))
        related_devices = searcher.async_search(ItemType.ENTITY, entity_id)
        if related_devices and "device" in related_devices:
            related_device_id = related_devices["device"].pop()
            if device_entry := dr.async_get(hass).async_get(related_device_id):
                res = device_entry.area_id or ""
    LOGGER.finest(
        "Entity.service._related_area, entity_id: %s, res: %s",
        entity_id,
        res
    )
    return res


def _related_integrations(hass: HomeAssistant, entity_id: str) -> set:
    LOGGER.finest("Entity.service._related_integrations called, entity_id: %s", entity_id)
    res = set()
    searcher = Searcher(hass, hass_entity.entity_sources(hass))
    related = searcher.async_search(ItemType.ENTITY, entity_id)
    if related and "integration" in related:
        res = related["integration"]
    LOGGER.finest(
        "Entity.service._related_integrations, entity_id: %s, res: %s",
        entity_id,
        res
    )
    return res


def get_single(hass: HomeAssistant, entity_id: str) -> DomikaEntityInfo | None:
    """Get single entity info."""
    LOGGER.finest("Entity.service.get_single called, entity_id: %s", entity_id)
    result = DomikaEntityInfo({})
    state = hass.states.get(entity_id)
    if not state:
        return None

    integrations = _related_integrations(hass, entity_id)
    if "mobile_app" in integrations:
        return None

    result.info["name"] = state.attributes.get(ATTR_FRIENDLY_NAME) or state.name
    area = _related_area(hass, entity_id)
    if area:
        result.info["area"] = _related_area(hass, entity_id)

    # Find out related entity ids, they will be used in the widget
    related_ids = {}
    if state.domain == "lock":
        related_ids = _related_lock(hass, entity_id)
    elif state.domain == "climate":
        related_ids = _related_climate(hass, entity_id)
    if related_ids:
        result.info["related"] = related_ids

    # Find out the capabilities of the entity, to be able to select widget size
    # appropriately.
    capabilities = set()
    if state.domain == Platform.LIGHT:
        capabilities = _capabilities_light(hass, entity_id)
    elif state.domain == Platform.CLIMATE:
        capabilities = _capabilities_climate(hass, entity_id)
    elif state.domain == Platform.COVER:
        capabilities = _capabilities_cover(hass, entity_id)
    elif state.domain == Platform.SENSOR:
        capabilities = _capabilities_sensor(hass, state)
    elif state.domain == Platform.BINARY_SENSOR:
        capabilities = _capabilities_binary_sensor(hass, state)
    elif state.domain == Platform.MEDIA_PLAYER:
        capabilities = _capabilities_player(hass, entity_id)
    elif state.domain == Platform.LOCK:
        if ATTR_DEVICE_CLASS in related_ids:
            capabilities = _capabilities_lock(entity_id, related_ids[ATTR_DEVICE_CLASS])
        else:
            capabilities = _capabilities_lock(entity_id, "")
    if capabilities:
        result.info["capabilities"] = capabilities

    LOGGER.finest(
        "Entity.service.get_single, entity_id: %s, result: %s",
        entity_id,
        result
    )
    return result


def get(hass: HomeAssistant, domains: list[str], include_hidden_disabled: bool) -> DomikaEntitiesList:
    entity_registry = er.async_get(hass)

    """Get names and related ids for all entities in specified domains."""
    LOGGER.finest("Entity.service.get called, entity_id: %s", domains)
    entity_ids = hass.states.async_entity_ids(domains)
    result = DomikaEntitiesList({})
    for entity_id in entity_ids:
        entity: RegistryEntry | None = entity_registry.entities.get(entity_id)
        if not include_hidden_disabled:
            if not entity or entity.hidden_by or entity.disabled_by:
                continue

        single = get_single(hass, entity_id)
        if single:
            if entity and entity.hidden_by:
                single.info["hidden"] = True
            if entity and entity.disabled_by:
                single.info["disabled"] = True
            result.entities[entity_id] = single.info
    LOGGER.finest(
        "Entity.service.get_single, domains: %s, result: %s",
        domains,
        result
    )
    return result
