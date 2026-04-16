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
