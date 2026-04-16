"""Setpoint adjustment policy implementation."""
import logging
from typing import Optional

from homeassistant.util import dt as dt_util

from .base import SetpointAdjustmentPolicy
from ..value_objects import HVACMode, ControlContext, Temperature

_LOGGER = logging.getLogger(__name__)


class IterativeSetpointAdjustmentPolicy(SetpointAdjustmentPolicy):
    """
    Iterative setpoint adjustment policy.

    Key principles:
    - Adjust setpoint by small steps (default 1°C)
    - Wait and observe dynamics before next adjustment
    - Don't adjust if good dynamics already present
    - Consider outdoor temperature for natural drift
    """

    def calculate_setpoint(
        self,
        mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        temp_rate: Optional[float],  # Short-term rate (1 minute)
        context: ControlContext,
    ) -> tuple[Temperature, str]:
        """
        Calculate setpoint using iterative adjustment logic.

        Args:
            mode: Current HVAC mode (HEAT/COOL/OFF)
            room_temp: Current room temperature
            target_temp: Target temperature
            temp_rate: Short-term temperature change rate (°C/hour)
            context: Full control context

        Returns:
            Tuple of (desired setpoint, reasoning string)
        """

        if mode == HVACMode.OFF:
            return target_temp, "Device off, setpoint = target"

        if mode not in (HVACMode.HEAT, HVACMode.COOL):
            return target_temp, f"Mode {mode.value} - using target as setpoint"

        # Get current setpoint on AC device
        current_setpoint = context.device_state.current_setpoint
        if current_setpoint is None:
            # No current setpoint, start with target
            return target_temp, "No current setpoint, starting with target"

        current_setpoint_value = current_setpoint.value

        # Calculate temperature error
        temp_error = float(room_temp - target_temp)

        # Check if we're in deadband (temperature is acceptable)
        in_deadband = abs(temp_error) <= context.deadband

        # Determine if we have good dynamics
        has_good_dynamics = False
        if temp_rate is not None and not in_deadband:
            # Good dynamics threshold: at least 0.5°C/hour movement in correct direction
            min_dynamics = 0.5

            if mode == HVACMode.COOL and temp_error > context.deadband:
                # Need cooling: good if temperature is decreasing
                has_good_dynamics = temp_rate < -min_dynamics
            elif mode == HVACMode.HEAT and temp_error < -context.deadband:
                # Need heating: good if temperature is increasing
                has_good_dynamics = temp_rate > min_dynamics

        # If we have good dynamics, keep current setpoint
        if has_good_dynamics:
            _LOGGER.debug(
                "Good dynamics detected: %.1f°C/h in %s mode, keeping setpoint %.1f",
                temp_rate,
                mode.value,
                current_setpoint_value,
            )
            return current_setpoint, f"Good dynamics ({temp_rate:.1f}°C/h), keeping setpoint"

        # If in deadband, keep current setpoint
        if in_deadband:
            return current_setpoint, f"In deadband (error={temp_error:.1f}°C), keeping setpoint"

        # Check if enough time passed since last adjustment
        if hasattr(context, 'last_setpoint_adjustment') and context.last_setpoint_adjustment is not None:
            # Ensure last_setpoint_adjustment is timezone-aware
            last_adjustment = context.last_setpoint_adjustment
            if last_adjustment.tzinfo is None:
                # Convert naive datetime to timezone-aware
                last_adjustment = dt_util.as_utc(last_adjustment)
                _LOGGER.warning("last_setpoint_adjustment was timezone-naive, converted to UTC")

            time_since_adjustment = (context.now - last_adjustment).total_seconds()
            adjustment_interval = getattr(context, 'setpoint_adjustment_interval', 120)

            if time_since_adjustment < adjustment_interval:
                remaining = adjustment_interval - time_since_adjustment
                _LOGGER.debug(
                    "Too soon to adjust setpoint: %.0fs since last adjustment (need %ds)",
                    time_since_adjustment,
                    adjustment_interval,
                )
                return current_setpoint, f"Wait {remaining:.0f}s before next adjustment"

        # Need to adjust setpoint
        setpoint_step = getattr(context, 'setpoint_step', 1.0)
        outdoor_temp = context.sensor_snapshot.outdoor_temperature.value

        # Determine adjustment direction and magnitude
        if mode == HVACMode.COOL:
            if temp_error > context.deadband:
                # Too hot, need more cooling -> decrease setpoint
                new_setpoint = current_setpoint_value - setpoint_step
                reason = f"Too hot (+{temp_error:.1f}°C), decrease setpoint by {setpoint_step}°C"

                # Consider outdoor temperature
                if outdoor_temp < target_temp.value - 2:
                    # Outdoor is cool, house will naturally cool down
                    # Be less aggressive
                    new_setpoint = current_setpoint_value - (setpoint_step * 0.5)
                    reason += " | Outdoor cool, reduced adjustment"

            else:
                # Too cold or overshooting, reduce cooling -> increase setpoint
                new_setpoint = current_setpoint_value + setpoint_step
                reason = f"Overshooting ({temp_error:.1f}°C), increase setpoint by {setpoint_step}°C"

        else:  # mode == HVACMode.HEAT
            if temp_error < -context.deadband:
                # Too cold, need more heating -> increase setpoint
                new_setpoint = current_setpoint_value + setpoint_step
                reason = f"Too cold ({temp_error:.1f}°C), increase setpoint by {setpoint_step}°C"

                # Consider outdoor temperature
                if outdoor_temp > target_temp.value + 2:
                    # Outdoor is warm, house will naturally warm up
                    # Be less aggressive
                    new_setpoint = current_setpoint_value + (setpoint_step * 0.5)
                    reason += " | Outdoor warm, reduced adjustment"

            else:
                # Too hot or overshooting, reduce heating -> decrease setpoint
                new_setpoint = current_setpoint_value - setpoint_step
                reason = f"Overshooting (+{temp_error:.1f}°C), decrease setpoint by {setpoint_step}°C"

        # Clamp to device capabilities
        clamped_setpoint = max(
            context.device_capabilities.min_setpoint.value,
            min(new_setpoint, context.device_capabilities.max_setpoint.value)
        )

        if new_setpoint != clamped_setpoint:
            reason += f" | Clamped to device limits"

        setpoint = Temperature(clamped_setpoint)

        _LOGGER.info(
            "Setpoint adjustment: %s mode, room=%.1f°C, target=%.1f°C, error=%.1f°C, "
            "current_setpoint=%.1f°C, new_setpoint=%.1f°C, rate=%s",
            mode.value,
            room_temp.value,
            target_temp.value,
            temp_error,
            current_setpoint_value,
            setpoint.value,
            f"{temp_rate:.1f}°C/h" if temp_rate is not None else "N/A",
        )

        return setpoint, reason


# Keep old class name for backward compatibility during migration
DynamicSetpointAdjustmentPolicy = IterativeSetpointAdjustmentPolicy
