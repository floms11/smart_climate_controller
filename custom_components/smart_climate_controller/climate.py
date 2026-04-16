"""Climate entity for Smart Climate Controller."""
import logging
from typing import Any, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_CONTROL_ACTIVE,
    ATTR_LAST_DECISION,
    ATTR_LAST_DECISION_REASON,
    ATTR_LAST_CONTROL_TIME,
    ATTR_LAST_MODE_CHANGE,
    ATTR_ROOM_TEMP_RATE,
    ATTR_OUTDOOR_TEMP,
    ATTR_DESIRED_MODE,
    ATTR_DESIRED_SETPOINT,
    ATTR_MODE_LOCKED_UNTIL,
    ATTR_COMMAND_LOCKED_UNTIL,
)
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Climate Controller climate entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([SmartClimateEntity(coordinator, entry)])


class SmartClimateEntity(CoordinatorEntity, ClimateEntity):
    """Smart Climate Controller entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_name = entry.data.get("zone_name", "Smart Climate Controller")

        self.entry = entry
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("room_temp")

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self.coordinator.config.get("target_temp")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.coordinator.controller_enabled:
            return HVACMode.OFF

        # Show the actual device mode when controller is active
        if self.coordinator.data is None:
            return HVACMode.AUTO

        device_mode = self.coordinator.data.get("device_mode")
        decision = self.coordinator.data.get("decision")

        # If we have a decision, show desired mode (what we want to achieve)
        if decision and decision.desired_mode:
            desired_mode_str = decision.desired_mode.value
            mode_map = {
                "off": HVACMode.OFF,
                "heat": HVACMode.HEAT,
                "cool": HVACMode.COOL,
                "auto": HVACMode.AUTO,
            }
            return mode_map.get(desired_mode_str, HVACMode.AUTO)

        # Fallback to actual device mode
        if device_mode:
            mode_map = {
                "off": HVACMode.AUTO,  # Show AUTO even if device is off (controller is active)
                "heat": HVACMode.HEAT,
                "cool": HVACMode.COOL,
                "auto": HVACMode.AUTO,
                "dry": HVACMode.AUTO,
                "fan_only": HVACMode.AUTO,
            }
            return mode_map.get(device_mode, HVACMode.AUTO)

        return HVACMode.AUTO

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.coordinator.config.get("min_room_temp", 16.0)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.coordinator.config.get("max_room_temp", 30.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if self.coordinator.data is None:
            return {}

        decision = self.coordinator.data.get("decision")
        diagnostics = self.coordinator.data.get("controller_diagnostics", {})

        attrs = {
            ATTR_CONTROL_ACTIVE: self.coordinator.controller_enabled,
            ATTR_OUTDOOR_TEMP: self.coordinator.data.get("outdoor_temp"),
        }

        if decision:
            attrs[ATTR_LAST_DECISION] = decision.decision_type.value
            attrs[ATTR_LAST_DECISION_REASON] = decision.reason
            attrs[ATTR_LAST_CONTROL_TIME] = decision.timestamp.isoformat()
            attrs[ATTR_DESIRED_MODE] = decision.desired_mode.value if decision.desired_mode else None
            attrs[ATTR_DESIRED_SETPOINT] = (
                decision.desired_setpoint.value if decision.desired_setpoint else None
            )

        if diagnostics:
            last_decision = diagnostics.get("last_decision", {})
            attrs[ATTR_LAST_MODE_CHANGE] = diagnostics.get("last_mode_change")
            attrs[ATTR_ROOM_TEMP_RATE] = None  # Could extract from history

        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Auto-enable controller when user sets temperature
        if not self.coordinator.controller_enabled:
            _LOGGER.info("Auto-enabling controller on temperature change")
            self.coordinator.set_controller_enabled(True)

        self.coordinator.set_target_temperature(temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            self.coordinator.set_controller_enabled(False)
        elif hvac_mode == HVACMode.AUTO:
            self.coordinator.set_controller_enabled(True)
        else:
            _LOGGER.warning("Only AUTO and OFF modes supported, got: %s", hvac_mode)
            return

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the controller."""
        self.coordinator.set_controller_enabled(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the controller."""
        self.coordinator.set_controller_enabled(False)
        await self.coordinator.async_request_refresh()
