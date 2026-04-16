"""Sensor entities for Smart Climate Controller."""
import logging
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Controller sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        OutdoorTemperatureSensor(coordinator, entry),
        DesiredSetpointSensor(coordinator, entry),
        ControlDecisionSensor(coordinator, entry),
        ActualDeviceModeSensor(coordinator, entry),
        DesiredHVACModeSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class SmartClimateSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Smart Climate Controller sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartClimateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = name
        self._sensor_type = sensor_type


class OutdoorTemperatureSensor(SmartClimateSensorBase):
    """Sensor showing outdoor temperature used for mode selection."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the outdoor temperature sensor."""
        super().__init__(coordinator, entry, "outdoor_temp", "Outdoor Temperature")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("outdoor_temp")


class DesiredSetpointSensor(SmartClimateSensorBase):
    """Sensor showing desired AC setpoint calculated by controller."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the desired setpoint sensor."""
        super().__init__(coordinator, entry, "desired_setpoint", "Desired AC Setpoint")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        decision = self.coordinator.data.get("decision")
        if decision and decision.desired_setpoint:
            return decision.desired_setpoint.value

        return None


class ControlDecisionSensor(SmartClimateSensorBase):
    """Sensor showing last control decision type."""

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the control decision sensor."""
        super().__init__(coordinator, entry, "control_decision", "Control Decision")

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        decision = self.coordinator.data.get("decision")
        if decision:
            return decision.decision_type.value

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        decision = self.coordinator.data.get("decision")
        if not decision:
            return {}

        return {
            "reason": decision.reason,
            "desired_mode": decision.desired_mode.value if decision.desired_mode else None,
            "desired_setpoint": decision.desired_setpoint.value if decision.desired_setpoint else None,
            "should_send_command": decision.should_send_command,
            "command_sent": self.coordinator.data.get("command_sent", False),
        }


class ActualDeviceModeSensor(SmartClimateSensorBase):
    """Sensor showing actual HVAC mode of the physical device."""

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the actual device mode sensor."""
        super().__init__(coordinator, entry, "actual_device_mode", "Actual Device Mode")

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        device_mode = self.coordinator.data.get("device_mode")
        if device_mode:
            # Make it more readable
            mode_names = {
                "off": "Off",
                "heat": "Heating",
                "cool": "Cooling",
                "auto": "Auto",
                "dry": "Dry",
                "fan_only": "Fan Only",
            }
            return mode_names.get(device_mode, device_mode.title())

        return None

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.coordinator.data is None:
            return "mdi:air-conditioner"

        device_mode = self.coordinator.data.get("device_mode")
        icon_map = {
            "off": "mdi:power-off",
            "heat": "mdi:fire",
            "cool": "mdi:snowflake",
            "auto": "mdi:autorenew",
            "dry": "mdi:water-percent",
            "fan_only": "mdi:fan",
        }
        return icon_map.get(device_mode, "mdi:air-conditioner")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        return {
            "device_setpoint": self.coordinator.data.get("device_setpoint"),
            "controller_enabled": self.coordinator.controller_enabled,
        }


class DesiredHVACModeSensor(SmartClimateSensorBase):
    """Sensor showing desired HVAC mode (heat or cool) that controller wants to use."""

    def __init__(self, coordinator: SmartClimateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the desired HVAC mode sensor."""
        super().__init__(coordinator, entry, "desired_hvac_mode", "Desired HVAC Mode")

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor - only Heat, Cool, or Off."""
        if self.coordinator.data is None:
            return None

        decision = self.coordinator.data.get("decision")
        if decision and decision.desired_mode:
            mode = decision.desired_mode.value
            # Only return actual operation modes
            if mode == "heat":
                return "Heat"
            elif mode == "cool":
                return "Cool"
            elif mode == "off":
                return "Off"
            else:
                # For other modes (auto, etc), return None or Off
                return "Off"

        return "Off"

    @property
    def icon(self) -> str:
        """Return the icon."""
        value = self.native_value
        if value == "Heat":
            return "mdi:fire"
        elif value == "Cool":
            return "mdi:snowflake"
        elif value == "Off":
            return "mdi:power-off"
        else:
            return "mdi:thermostat"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        attrs = {}

        # Add manual mode override info
        if self.coordinator.manual_mode_override:
            attrs["mode_source"] = "Manual"
            attrs["manual_override"] = self.coordinator.manual_mode_override
        else:
            attrs["mode_source"] = "Auto"

        # Add decision reason
        decision = self.coordinator.data.get("decision")
        if decision:
            attrs["reason"] = decision.reason

        return attrs
