"""Home Assistant command sender."""
import asyncio
import logging
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ATTR_HVAC_MODE,
)

from ..application.commands import SetClimateCommand

_LOGGER = logging.getLogger(__name__)


class HACommandSender:
    """Sends commands to Home Assistant entities."""

    def __init__(self, hass: HomeAssistant):
        """Initialize command sender."""
        self.hass = hass

    async def send_climate_command(
        self,
        command: SetClimateCommand,
        entity_id: str,
    ) -> bool:
        """
        Send climate control command to HA entity.

        Returns True if command was sent successfully.
        """
        try:
            service_data = {"entity_id": entity_id}

            # Determine if we need to set mode, temperature, or both
            need_mode = True
            need_temp = command.target_temperature is not None

            if need_mode and need_temp:
                # Set mode and temperature separately for better compatibility
                # Some integrations don't support setting both in one call

                # First, set the mode
                mode_data = {"entity_id": entity_id, ATTR_HVAC_MODE: command.hvac_mode.value}
                _LOGGER.info(
                    "Setting climate %s: mode=%s",
                    entity_id,
                    command.hvac_mode.value,
                )
                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_HVAC_MODE,
                    mode_data,
                    blocking=True,
                )

                # Small delay for device to process mode change
                await asyncio.sleep(0.5)

                # Then, set the temperature
                temp_data = {"entity_id": entity_id, ATTR_TEMPERATURE: command.target_temperature.value}
                _LOGGER.info(
                    "Setting climate %s: temp=%.1f",
                    entity_id,
                    command.target_temperature.value,
                )
                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_TEMPERATURE,
                    temp_data,
                    blocking=True,
                )

            elif need_mode:
                # Set only mode
                service_data[ATTR_HVAC_MODE] = command.hvac_mode.value

                _LOGGER.info(
                    "Setting climate %s: mode=%s",
                    entity_id,
                    command.hvac_mode.value,
                )

                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_HVAC_MODE,
                    service_data,
                    blocking=True,
                )

            elif need_temp:
                # Set only temperature
                service_data[ATTR_TEMPERATURE] = command.target_temperature.value

                _LOGGER.info(
                    "Setting climate %s: temp=%.1f",
                    entity_id,
                    command.target_temperature.value,
                )

                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_TEMPERATURE,
                    service_data,
                    blocking=True,
                )

            return True

        except Exception as err:
            _LOGGER.error(
                "Failed to send command to %s: %s",
                entity_id,
                err,
                exc_info=True,
            )
            return False
