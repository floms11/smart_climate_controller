"""Safety policy implementation."""
import logging

from .base import SafetyPolicy
from ..value_objects import ControlContext, HVACMode

_LOGGER = logging.getLogger(__name__)


class BasicSafetyPolicy(SafetyPolicy):
    """
    Implements basic safety checks:
    - Temperature hard limits
    - Sensor validity
    - Device availability
    """

    def should_emergency_stop(
        self,
        context: ControlContext,
    ) -> tuple[bool, str]:
        """Check if device should be stopped for safety reasons."""

        # Check if device is available
        if not context.device_state.is_available:
            return True, "Device unavailable"

        room_temp = context.sensor_snapshot.room_temperature

        # Check hard temperature limits
        if room_temp < context.min_room_temp:
            _LOGGER.error(
                "Room temperature %.1f°C below minimum %.1f°C - emergency stop",
                room_temp.value,
                context.min_room_temp.value,
            )
            return True, f"Room temp {room_temp.value:.1f}°C below minimum"

        if room_temp > context.max_room_temp:
            _LOGGER.error(
                "Room temperature %.1f°C above maximum %.1f°C - emergency stop",
                room_temp.value,
                context.max_room_temp.value,
            )
            return True, f"Room temp {room_temp.value:.1f}°C above maximum"

        # Check for dangerous heating when already too hot
        if (
            room_temp > context.target_temperature + context.deadband * 3
            and context.device_state.hvac_mode == HVACMode.HEAT
        ):
            _LOGGER.warning(
                "Room significantly overheated (%.1f°C) while heating - stopping",
                room_temp.value,
            )
            return True, "Overheating detected while in heating mode"

        # Check for dangerous cooling when already too cold
        if (
            room_temp < context.target_temperature - context.deadband * 3
            and context.device_state.hvac_mode == HVACMode.COOL
        ):
            _LOGGER.warning(
                "Room significantly overcooled (%.1f°C) while cooling - stopping",
                room_temp.value,
            )
            return True, "Overcooling detected while in cooling mode"

        # All safety checks passed
        return False, "All safety checks passed"
