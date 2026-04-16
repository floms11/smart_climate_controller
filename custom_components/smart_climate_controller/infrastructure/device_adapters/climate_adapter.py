"""Adapter for standard HA climate entities."""
import logging
from typing import Optional

from homeassistant.core import HomeAssistant

from .base import ClimateDeviceAdapter
from ..ha_state import HAStateReader
from ..ha_commands import HACommandSender
from ...application.commands import SetClimateCommand
from ...domain.value_objects import HVACMode, Temperature

_LOGGER = logging.getLogger(__name__)


class ClimateEntityAdapter(ClimateDeviceAdapter):
    """Adapter for standard Home Assistant climate entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
    ):
        """Initialize climate entity adapter."""
        self.hass = hass
        self.entity_id = entity_id
        self.state_reader = HAStateReader(hass)
        self.command_sender = HACommandSender(hass)

    async def get_current_mode(self) -> str:
        """Get current HVAC mode."""
        state = self.state_reader.get_climate_state(self.entity_id)
        if state is None:
            return "off"
        return state["hvac_mode"]

    async def get_current_setpoint(self) -> Optional[float]:
        """Get current temperature setpoint."""
        state = self.state_reader.get_climate_state(self.entity_id)
        if state is None:
            return None
        return state["target_temperature"]

    async def get_supported_modes(self) -> list[str]:
        """Get list of supported HVAC modes."""
        state = self.state_reader.get_climate_state(self.entity_id)
        if state is None:
            return ["off"]
        return state["hvac_modes"]

    async def get_temperature_limits(self) -> tuple[float, float]:
        """Get min and max temperature limits."""
        state = self.state_reader.get_climate_state(self.entity_id)
        if state is None:
            return (16.0, 30.0)
        return (state["min_temp"], state["max_temp"])

    async def is_available(self) -> bool:
        """Check if device is available."""
        state = self.state_reader.get_climate_state(self.entity_id)
        if state is None:
            return False
        return state["is_available"]

    async def set_mode(self, mode: str) -> bool:
        """Set HVAC mode."""
        command = SetClimateCommand(
            device_id=self.entity_id,
            hvac_mode=HVACMode(mode),
            target_temperature=None,
        )
        return await self.command_sender.send_climate_command(
            command,
            self.entity_id,
        )

    async def set_temperature(self, temperature: float) -> bool:
        """Set target temperature."""
        current_mode = await self.get_current_mode()
        command = SetClimateCommand(
            device_id=self.entity_id,
            hvac_mode=HVACMode(current_mode),
            target_temperature=Temperature(temperature),
        )
        return await self.command_sender.send_climate_command(
            command,
            self.entity_id,
        )

    async def set_mode_and_temperature(self, mode: str, temperature: float) -> bool:
        """Set both mode and temperature."""
        command = SetClimateCommand(
            device_id=self.entity_id,
            hvac_mode=HVACMode(mode),
            target_temperature=Temperature(temperature),
        )
        return await self.command_sender.send_climate_command(
            command,
            self.entity_id,
        )
