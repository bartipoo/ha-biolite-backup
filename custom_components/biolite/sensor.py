"""Sensors for BioLite Backup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BioliteCoordinator, BioliteData


@dataclass(frozen=True, kw_only=True)
class BioliteSensorDescription(SensorEntityDescription):
    """Describes one BioLite sensor, keyed off a BioliteData snapshot."""

    value_fn: Callable[[BioliteData], float | None] = lambda data: None


def _stage_watts(block_getter: Callable[[BioliteData], object], stage: str):
    def _get(data: BioliteData) -> float | None:
        block = block_getter(data)
        if block is None:
            return None
        stage_rec = block.stages.get(stage)
        return None if stage_rec is None else stage_rec.value

    return _get


def _block_attr(block_getter: Callable[[BioliteData], object], attr: str):
    def _get(data: BioliteData) -> float | None:
        block = block_getter(data)
        return None if block is None else getattr(block, attr)

    return _get


SENSOR_DESCRIPTIONS: tuple[BioliteSensorDescription, ...] = (
    BioliteSensorDescription(
        key="core_soc",
        name="Core Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_block_attr(lambda d: d.core, "soc"),
    ),
    BioliteSensorDescription(
        key="extend_soc",
        name="Extend Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_block_attr(lambda d: d.extend, "soc"),
    ),
    BioliteSensorDescription(
        key="core_temperature",
        name="Core Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_block_attr(lambda d: d.core, "temperature"),
    ),
    BioliteSensorDescription(
        key="ac_in_power",
        name="AC Input Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_stage_watts(lambda d: d.core, "ac_in"),
    ),
    BioliteSensorDescription(
        key="ac_out_power",
        name="AC Output Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_stage_watts(lambda d: d.core, "ac_out"),
    ),
    BioliteSensorDescription(
        key="core_dcdc_power",
        name="Core DC-DC Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_stage_watts(lambda d: d.core, "dcdc_link"),
    ),
    BioliteSensorDescription(
        key="gate_link_power",
        name="Core/Extend Gate Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_stage_watts(lambda d: d.extend, "gate_link"),
    ),
    BioliteSensorDescription(
        key="core_capacity",
        name="Core Rated Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_block_attr(lambda d: d.core, "capacity_wh"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BioliteCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BioliteSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BioliteSensor(CoordinatorEntity[BioliteCoordinator], SensorEntity):
    """A single BioLite metric."""

    entity_description: BioliteSensorDescription

    def __init__(
        self,
        coordinator: BioliteCoordinator,
        entry: ConfigEntry,
        description: BioliteSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.node_id)},
            name="BioLite Backup",
            manufacturer="BioLite",
            model="HomeCharge",
        )

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator.data)
