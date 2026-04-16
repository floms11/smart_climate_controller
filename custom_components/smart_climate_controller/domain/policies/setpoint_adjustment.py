"""Setpoint adjustment policy implementation."""
import logging
from typing import Optional

from .base import SetpointAdjustmentPolicy
from ..value_objects import HVACMode, ControlContext, Temperature

_LOGGER = logging.getLogger(__name__)


class DynamicSetpointAdjustmentPolicy(SetpointAdjustmentPolicy):
    """
    Calculates device setpoint using dynamic offset based on:
    - Temperature error (deviation from target)
    - Rate of temperature change
    - Current HVAC mode

    Key principle: Modulate setpoint to achieve gradual convergence,
    not aggressive on/off cycling.
    """

    def calculate_setpoint(
        self,
        mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        temp_rate: Optional[float],
        context: ControlContext,
    ) -> tuple[Temperature, str]:
        """Calculate optimal setpoint for gradual temperature control."""

        if mode == HVACMode.OFF:
            return target_temp, "Device off, setpoint = target"

        if mode not in (HVACMode.HEAT, HVACMode.COOL):
            return target_temp, f"Mode {mode.value} - using target as setpoint"

        # Calculate temperature error
        temp_error = float(room_temp - target_temp)

        # Base offset direction depends on mode
        if mode == HVACMode.COOL:
            # Cooling: set AC colder than target
            base_direction = -1
        elif mode == HVACMode.HEAT:
            # Heating: set AC warmer than target
            base_direction = 1
        else:
            base_direction = 0

        # Start with base offset
        total_offset = context.base_offset * base_direction

        # Add dynamic offset based on error magnitude
        # Larger error -> larger offset (more aggressive)
        error_based_offset = 0.0
        if abs(temp_error) > context.deadband:
            # Error outside deadband - add proportional offset
            error_magnitude = abs(temp_error) - context.deadband
            error_based_offset = min(error_magnitude * 0.5, context.max_dynamic_offset)
            error_based_offset *= base_direction

        # Add rate-based offset if rate is available
        rate_based_offset = 0.0
        if temp_rate is not None:
            # If temperature is changing in undesired direction, increase offset
            if mode == HVACMode.COOL and temp_rate > 0:
                # Room warming while cooling - increase cooling power
                rate_based_offset = -min(
                    abs(temp_rate) * context.dynamic_rate_factor,
                    context.max_dynamic_offset
                )
            elif mode == HVACMode.HEAT and temp_rate < 0:
                # Room cooling while heating - increase heating power
                rate_based_offset = min(
                    abs(temp_rate) * context.dynamic_rate_factor,
                    context.max_dynamic_offset
                )

        # Combine offsets
        total_offset += error_based_offset + rate_based_offset

        # Calculate final setpoint
        raw_setpoint = target_temp.value + total_offset

        # Clamp to device capabilities
        clamped_setpoint = max(
            context.device_capabilities.min_setpoint.value,
            min(raw_setpoint, context.device_capabilities.max_setpoint.value)
        )

        setpoint = Temperature(clamped_setpoint)

        # Build reason string
        reason_parts = [f"base={context.base_offset * base_direction:.1f}"]
        if error_based_offset != 0:
            reason_parts.append(f"error={error_based_offset:.1f}")
        if rate_based_offset != 0:
            reason_parts.append(f"rate={rate_based_offset:.1f}")
        reason_parts.append(f"total={total_offset:.1f}")

        if raw_setpoint != clamped_setpoint:
            reason_parts.append("clamped")

        reason = f"Setpoint calculation: {', '.join(reason_parts)}"

        _LOGGER.debug(
            "Setpoint for %s: target=%.1f, room=%.1f, error=%.1f, rate=%s, setpoint=%.1f",
            mode.value,
            target_temp.value,
            room_temp.value,
            temp_error,
            f"{temp_rate:.2f}" if temp_rate is not None else "N/A",
            setpoint.value,
        )

        return setpoint, reason
