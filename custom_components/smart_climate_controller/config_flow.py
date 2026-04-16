"""Config flow for Smart Climate Controller."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AC_NAME,
    CONF_AC_UNITS,
    CONF_CLIMATE_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_MAJOR_CORRECTION_VALUE,
    CONF_MAJOR_DEVIATION_THRESHOLD,
    CONF_MIN_MODE_SWITCH_INTERVAL,
    CONF_MIN_POWER_SWITCH_INTERVAL,
    CONF_MINOR_CORRECTION_HYSTERESIS,
    CONF_MINOR_CORRECTION_VALUE,
    CONF_OUTDOOR_TEMP_COOL_ONLY,
    CONF_OUTDOOR_TEMP_HEAT_ONLY,
    CONF_OUTDOOR_TEMP_SENSOR,
    DEFAULT_MAJOR_CORRECTION_VALUE,
    DEFAULT_MAJOR_DEVIATION_THRESHOLD,
    DEFAULT_MIN_MODE_SWITCH_INTERVAL,
    DEFAULT_MIN_POWER_SWITCH_INTERVAL,
    DEFAULT_MINOR_CORRECTION_HYSTERESIS,
    DEFAULT_MINOR_CORRECTION_VALUE,
    DEFAULT_OUTDOOR_TEMP_COOL_ONLY,
    DEFAULT_OUTDOOR_TEMP_HEAT_ONLY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmartClimateControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Climate Controller."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._ac_units = []
        self._outdoor_temp_sensor = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step - outdoor sensor."""
        errors = {}

        if user_input is not None:
            self._outdoor_temp_sensor = user_input[CONF_OUTDOOR_TEMP_SENSOR]
            return await self.async_step_add_ac()

        schema = vol.Schema(
            {
                vol.Required(CONF_OUTDOOR_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_ac(self, user_input=None):
        """Handle adding an AC unit."""
        errors = {}

        if user_input is not None:
            # Validate AC name is unique
            ac_name = user_input[CONF_AC_NAME]
            if any(ac[CONF_AC_NAME] == ac_name for ac in self._ac_units):
                errors[CONF_AC_NAME] = "duplicate_ac_name"
            else:
                # Add outdoor sensor to each AC unit
                ac_unit = user_input.copy()
                ac_unit[CONF_OUTDOOR_TEMP_SENSOR] = self._outdoor_temp_sensor
                self._ac_units.append(ac_unit)
                return await self.async_step_add_another()

        schema = vol.Schema(
            {
                vol.Required(CONF_AC_NAME): selector.TextSelector(),
                vol.Required(CONF_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_INDOOR_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }
        )

        return self.async_show_form(
            step_id="add_ac",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_another(self, user_input=None):
        """Ask if user wants to add another AC unit."""
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_add_ac()
            return await self.async_step_global_settings()

        schema = vol.Schema(
            {
                vol.Required("add_another", default=True): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="add_another",
            data_schema=schema,
            description_placeholders={
                "ac_count": str(len(self._ac_units)),
            },
        )

    async def async_step_global_settings(self, user_input=None):
        """Handle global settings."""
        if user_input is not None:
            return self.async_create_entry(
                title="Smart Climate Controller",
                data={
                    CONF_AC_UNITS: self._ac_units,
                    CONF_OUTDOOR_TEMP_SENSOR: self._outdoor_temp_sensor,
                },
                options=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OUTDOOR_TEMP_HEAT_ONLY,
                    default=DEFAULT_OUTDOOR_TEMP_HEAT_ONLY,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-20, max=30, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_OUTDOOR_TEMP_COOL_ONLY,
                    default=DEFAULT_OUTDOOR_TEMP_COOL_ONLY,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=40, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MINOR_CORRECTION_HYSTERESIS,
                    default=DEFAULT_MINOR_CORRECTION_HYSTERESIS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=2.0, step=0.1, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MINOR_CORRECTION_VALUE,
                    default=DEFAULT_MINOR_CORRECTION_VALUE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=15, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MAJOR_CORRECTION_VALUE,
                    default=DEFAULT_MAJOR_CORRECTION_VALUE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=20, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MAJOR_DEVIATION_THRESHOLD,
                    default=DEFAULT_MAJOR_DEVIATION_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5, max=3.0, step=0.1, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MIN_MODE_SWITCH_INTERVAL,
                    default=DEFAULT_MIN_MODE_SWITCH_INTERVAL,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=3600, step=60, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    CONF_MIN_POWER_SWITCH_INTERVAL,
                    default=DEFAULT_MIN_POWER_SWITCH_INTERVAL,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=1800, step=60, unit_of_measurement="s"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="global_settings",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SmartClimateControllerOptionsFlow(config_entry)


class SmartClimateControllerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Smart Climate Controller."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_global_settings(user_input)

    async def async_step_global_settings(self, user_input=None):
        """Handle global settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OUTDOOR_TEMP_HEAT_ONLY,
                    default=options.get(
                        CONF_OUTDOOR_TEMP_HEAT_ONLY, DEFAULT_OUTDOOR_TEMP_HEAT_ONLY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-20, max=30, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_OUTDOOR_TEMP_COOL_ONLY,
                    default=options.get(
                        CONF_OUTDOOR_TEMP_COOL_ONLY, DEFAULT_OUTDOOR_TEMP_COOL_ONLY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=40, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MINOR_CORRECTION_HYSTERESIS,
                    default=options.get(
                        CONF_MINOR_CORRECTION_HYSTERESIS,
                        DEFAULT_MINOR_CORRECTION_HYSTERESIS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=2.0, step=0.1, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MINOR_CORRECTION_VALUE,
                    default=options.get(
                        CONF_MINOR_CORRECTION_VALUE, DEFAULT_MINOR_CORRECTION_VALUE
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=15, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MAJOR_CORRECTION_VALUE,
                    default=options.get(
                        CONF_MAJOR_CORRECTION_VALUE, DEFAULT_MAJOR_CORRECTION_VALUE
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=20, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MAJOR_DEVIATION_THRESHOLD,
                    default=options.get(
                        CONF_MAJOR_DEVIATION_THRESHOLD, DEFAULT_MAJOR_DEVIATION_THRESHOLD
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5, max=3.0, step=0.1, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    CONF_MIN_MODE_SWITCH_INTERVAL,
                    default=options.get(
                        CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=3600, step=60, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    CONF_MIN_POWER_SWITCH_INTERVAL,
                    default=options.get(
                        CONF_MIN_POWER_SWITCH_INTERVAL, DEFAULT_MIN_POWER_SWITCH_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=1800, step=60, unit_of_measurement="s"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="global_settings",
            data_schema=schema,
        )
