"""Sensor platform for the inio lamp."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import InioConfigEntry, InioCoordinator, InioData
from .entity import InioEntity

MODE_OPTIONS = ["off", "static", "connected"]
ADDON_OPTIONS = ["none", "boost", "relax", "scenario"]


@dataclass(frozen=True, kw_only=True)
class InioSensorDescription(SensorEntityDescription):
    """Describes an inio sensor."""

    value_fn: Callable[[InioData], str | float | None]


SENSORS: tuple[InioSensorDescription, ...] = (
    InioSensorDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=MODE_OPTIONS,
        value_fn=lambda data: (
            data.mode.lower() if data.mode.lower() in MODE_OPTIONS else None
        ),
    ),
    InioSensorDescription(
        key="addon",
        translation_key="addon",
        device_class=SensorDeviceClass.ENUM,
        options=ADDON_OPTIONS,
        value_fn=lambda data: (
            data.addon.lower() if data.addon.lower() in ADDON_OPTIONS else None
        ),
    ),
    InioSensorDescription(
        key="warm_duty",
        translation_key="warm_duty",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda data: data.warm,
    ),
    InioSensorDescription(
        key="cold_duty",
        translation_key="cold_duty",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda data: data.cold,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lamp's sensors."""
    async_add_entities(
        InioSensor(entry.runtime_data, entry, description) for description in SENSORS
    )


class InioSensor(InioEntity, SensorEntity):
    """A sensor reading from the lamp."""

    entity_description: InioSensorDescription

    def __init__(
        self,
        coordinator: InioCoordinator,
        entry: InioConfigEntry,
        description: InioSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
