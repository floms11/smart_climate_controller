"""Config flow for Smart Climate Controller."""
import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    DOMAIN,
    CONF_ZONE_NAME,
    CONF_CLIMATE_ENTITY,
    CONF_ROOM_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_TARGET_TEMP,
    CONF_DEADBAND,
    CONF_MIN_ROOM_TEMP,
    CONF_MAX_ROOM_TEMP,
    CONF_MIN_AC_SETPOINT,
    CONF_MAX_AC_SETPOINT,
    CONF_BASE_OFFSET,
    CONF_DYNAMIC_RATE_FACTOR,
    CONF_MAX_DYNAMIC_OFFSET,
    CONF_OUTDOOR_HEAT_THRESHOLD,
    CONF_OUTDOOR_COOL_THRESHOLD,
    CONF_MODE_SWITCH_HYSTERESIS,
    CONF_MIN_COMMAND_INTERVAL,
    CONF_MIN_MODE_SWITCH_INTERVAL,
    CONF_CONTROL_INTERVAL,
    CONF_ENABLE_DEBUG_SENSORS,
    DEFAULT_ZONE_NAME,
    DEFAULT_TARGET_TEMP,
    DEFAULT_DEADBAND,
    DEFAULT_MIN_ROOM_TEMP,
    DEFAULT_MAX_ROOM_TEMP,
    DEFAULT_MIN_AC_SETPOINT,
    DEFAULT_MAX_AC_SETPOINT,
    DEFAULT_BASE_OFFSET,
    DEFAULT_DYNAMIC_RATE_FACTOR,
    DEFAULT_MAX_DYNAMIC_OFFSET,
    DEFAULT_OUTDOOR_HEAT_THRESHOLD,
    DEFAULT_OUTDOOR_COOL_THRESHOLD,
    DEFAULT_MODE_SWITCH_HYSTERESIS,
    DEFAULT_MIN_COMMAND_INTERVAL,
    DEFAULT_MIN_MODE_SWITCH_INTERVAL,
    DEFAULT_CONTROL_INTERVAL,
    DEFAULT_ENABLE_DEBUG_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


class SmartClimateControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Climate Controller."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate entities exist
            climate_entity = user_input[CONF_CLIMATE_ENTITY]
            room_sensor = user_input[CONF_ROOM_TEMP_SENSOR]
            outdoor_sensor = user_input[CONF_OUTDOOR_TEMP_SENSOR]

            if not self.hass.states.get(climate_entity):
                errors[CONF_CLIMATE_ENTITY] = "entity_not_found"
            if not self.hass.states.get(room_sensor):
                errors[CONF_ROOM_TEMP_SENSOR] = "entity_not_found"
            if not self.hass.states.get(outdoor_sensor):
                errors[CONF_OUTDOOR_TEMP_SENSOR] = "entity_not_found"

            if not errors:
                # Set defaults for advanced options
                user_input.setdefault(CONF_DEADBAND, DEFAULT_DEADBAND)
                user_input.setdefault(CONF_MIN_ROOM_TEMP, DEFAULT_MIN_ROOM_TEMP)
                user_input.setdefault(CONF_MAX_ROOM_TEMP, DEFAULT_MAX_ROOM_TEMP)
                user_input.setdefault(CONF_MIN_AC_SETPOINT, DEFAULT_MIN_AC_SETPOINT)
                user_input.setdefault(CONF_MAX_AC_SETPOINT, DEFAULT_MAX_AC_SETPOINT)
                user_input.setdefault(CONF_BASE_OFFSET, DEFAULT_BASE_OFFSET)
                user_input.setdefault(CONF_DYNAMIC_RATE_FACTOR, DEFAULT_DYNAMIC_RATE_FACTOR)
                user_input.setdefault(CONF_MAX_DYNAMIC_OFFSET, DEFAULT_MAX_DYNAMIC_OFFSET)
                user_input.setdefault(CONF_OUTDOOR_HEAT_THRESHOLD, DEFAULT_OUTDOOR_HEAT_THRESHOLD)
                user_input.setdefault(CONF_OUTDOOR_COOL_THRESHOLD, DEFAULT_OUTDOOR_COOL_THRESHOLD)
                user_input.setdefault(CONF_MODE_SWITCH_HYSTERESIS, DEFAULT_MODE_SWITCH_HYSTERESIS)
                user_input.setdefault(CONF_MIN_COMMAND_INTERVAL, DEFAULT_MIN_COMMAND_INTERVAL)
                user_input.setdefault(CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL)
                user_input.setdefault(CONF_CONTROL_INTERVAL, DEFAULT_CONTROL_INTERVAL)
                user_input.setdefault(CONF_ENABLE_DEBUG_SENSORS, DEFAULT_ENABLE_DEBUG_SENSORS)

                return self.async_create_entry(
                    title=user_input[CONF_ZONE_NAME],
                    data=user_input,
                )

        data_schema = vol.Schema({
            vol.Required(CONF_ZONE_NAME, default=DEFAULT_ZONE_NAME): TextSelector(),
            vol.Required(CONF_CLIMATE_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="climate")
            ),
            vol.Required(CONF_ROOM_TEMP_SENSOR): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_OUTDOOR_TEMP_SENSOR): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): NumberSelector(
                NumberSelectorConfig(min=10, max=35, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return SmartClimateControllerOptionsFlow(config_entry)


class SmartClimateControllerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[dict[str, Any]] = None):
        """Manage the options."""
        if user_input is not None:
            # Update config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            return self.async_create_entry(title="", data={})

        # Get current values
        data = self.config_entry.data

        options_schema = vol.Schema({
            vol.Required(
                CONF_TARGET_TEMP,
                default=data.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)
            ): NumberSelector(
                NumberSelectorConfig(min=10, max=35, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_DEADBAND,
                default=data.get(CONF_DEADBAND, DEFAULT_DEADBAND)
            ): NumberSelector(
                NumberSelectorConfig(min=0.1, max=5.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_MIN_ROOM_TEMP,
                default=data.get(CONF_MIN_ROOM_TEMP, DEFAULT_MIN_ROOM_TEMP)
            ): NumberSelector(
                NumberSelectorConfig(min=5, max=25, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_MAX_ROOM_TEMP,
                default=data.get(CONF_MAX_ROOM_TEMP, DEFAULT_MAX_ROOM_TEMP)
            ): NumberSelector(
                NumberSelectorConfig(min=20, max=40, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_BASE_OFFSET,
                default=data.get(CONF_BASE_OFFSET, DEFAULT_BASE_OFFSET)
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=10, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_OUTDOOR_HEAT_THRESHOLD,
                default=data.get(CONF_OUTDOOR_HEAT_THRESHOLD, DEFAULT_OUTDOOR_HEAT_THRESHOLD)
            ): NumberSelector(
                NumberSelectorConfig(min=-10, max=25, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_OUTDOOR_COOL_THRESHOLD,
                default=data.get(CONF_OUTDOOR_COOL_THRESHOLD, DEFAULT_OUTDOOR_COOL_THRESHOLD)
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=35, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_MODE_SWITCH_HYSTERESIS,
                default=data.get(CONF_MODE_SWITCH_HYSTERESIS, DEFAULT_MODE_SWITCH_HYSTERESIS)
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=5, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")
            ),
            vol.Required(
                CONF_MIN_MODE_SWITCH_INTERVAL,
                default=data.get(CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL)
            ): NumberSelector(
                NumberSelectorConfig(min=300, max=7200, step=300, mode=NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
            vol.Required(
                CONF_CONTROL_INTERVAL,
                default=data.get(CONF_CONTROL_INTERVAL, DEFAULT_CONTROL_INTERVAL)
            ): NumberSelector(
                NumberSelectorConfig(min=30, max=300, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
