"""Binary sensors for BioLite Backup."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BioliteCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BioliteCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BioliteConnectivitySensor(coordinator, entry),
            BioliteOnBatterySensor(coordinator, entry),
        ]
    )


def _device_info(coordinator: BioliteCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.node_id)},
        name="BioLite Backup",
        manufacturer="BioLite",
        model="HomeCharge",
    )


class BioliteConnectivitySensor(CoordinatorEntity[BioliteCoordinator], BinarySensorEntity):
    """Whether the BioLite unit is currently online in the cloud."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Connectivity"

    def __init__(self, coordinator: BioliteCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connectivity"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.connected


class BioliteOnBatterySensor(CoordinatorEntity[BioliteCoordinator], BinarySensorEntity):
    """Whether output is currently being sourced from the battery inverter
    rather than passed straight through from the grid.

    Backed by the `flag` byte on the Core block's "ac_out" power stage --
    confirmed empirically to flip 0 (grid passthrough) -> 1 (battery
    inverter sourced) exactly when the wall plug is pulled during a load
    test. Power-level heuristics (e.g. "ac_in near zero") don't work here:
    ac_in tracks charging current, which is legitimately 0 whenever the
    battery is already full, even with the grid live and passing straight
    through to the load.
    """

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_name = "On Battery"

    def __init__(self, coordinator: BioliteCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_on_battery"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        core = self.coordinator.data.core
        if core is None:
            return None
        ac_out = core.stages.get("ac_out")
        return None if ac_out is None else ac_out.flag == 1
