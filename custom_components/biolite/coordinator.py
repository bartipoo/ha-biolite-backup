"""Data update coordinator for BioLite Backup."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BioliteApiClient, BioliteApiError
from .blob_parser import DeviceStateBlock, parse_device_state
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BioliteData:
    """Snapshot of everything we polled for one update cycle."""

    def __init__(self, connected: bool, blocks: list[DeviceStateBlock]) -> None:
        self.connected = connected
        self.blocks = blocks
        # Match blocks by which power stages they contain rather than by
        # position -- see blob_parser.parse_device_state docstring.
        self.core: DeviceStateBlock | None = next(
            (b for b in blocks if "ac_in" in b.stages), None
        )
        self.extend: DeviceStateBlock | None = next(
            (b for b in blocks if b is not self.core and "gate_link" in b.stages), None
        )


class BioliteCoordinator(DataUpdateCoordinator[BioliteData]):
    """Polls BioLite's cloud API and parses the device-state blob."""

    def __init__(self, hass: HomeAssistant, client: BioliteApiClient, node_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="biolite",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._client = client
        self._node_id = node_id

    @property
    def node_id(self) -> str:
        return self._node_id

    async def _async_update_data(self) -> BioliteData:
        try:
            status = await self._client.async_get_status(self._node_id)
            params = await self._client.async_get_params(self._node_id)
        except BioliteApiError as err:
            raise UpdateFailed(str(err)) from err

        connected = bool(status.get("connectivity", {}).get("connected", False))
        device_state_b64 = params.get("HomeCharge", {}).get("device-state")
        blocks = parse_device_state(device_state_b64) if device_state_b64 else []
        return BioliteData(connected=connected, blocks=blocks)
