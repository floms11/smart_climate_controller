"""Mode selection policy implementation."""
import logging
from typing import Optional

from .base import ModeSelectionPolicy
from ..value_objects import HVACMode, ControlContext, Temperature

_LOGGER = logging.getLogger(__name__)


class IntelligentModeSelectionPolicy(ModeSelectionPolicy):
    """
    Intelligent mode selection with setpoint correction awareness.

    Key principles:
    - Try setpoint correction before mode switching when possible
    - Use outdoor temperature to understand natural temperature drift
    - Use long-term dynamics to detect if current mode is ineffective
    - Only switch modes when necessary
    - Implement hysteresis to prevent oscillation
    - Respect minimum mode switch intervals
    """

    def select_mode(
        self,
        current_mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        outdoor_temp: Temperature,
        context: ControlContext,
    ) -> tuple[HVACMode, str]:
        """Select HVAC mode with intelligent switching logic."""

        # Check if controller is disabled
        if not context.controller_enabled:
            return HVACMode.OFF, "Controller disabled"

        # Check for manual mode override (highest priority)
        if context.manual_mode_override:
            _LOGGER.info("Manual mode override active: %s", context.manual_mode_override)
            if context.manual_mode_override == "heat":
                if not context.device_capabilities.can_heat:
                    _LOGGER.warning("Manual HEAT mode requested but device cannot heat")
                    return current_mode, "Manual HEAT mode requested but device cannot heat"
                return HVACMode.HEAT, "Manual mode override: HEAT"
            elif context.manual_mode_override == "cool":
                if not context.device_capabilities.can_cool:
                    _LOGGER.warning("Manual COOL mode requested but device cannot cool")
                    return current_mode, "Manual COOL mode requested but device cannot cool"
                return HVACMode.COOL, "Manual mode override: COOL"

        # Check mode switch timing lock
        if not self._can_switch_mode(context):
            time_remaining = (
                context.min_mode_switch_interval -
                (context.now - context.last_mode_change).total_seconds()
            )
            return current_mode, f"Mode switch locked for {time_remaining:.0f}s more"

        # Calculate temperature deviation
        temp_error = float(room_temp - target_temp)

        # Check if in deadband
        in_deadband = abs(temp_error) <= context.deadband

        # If in deadband, preserve current mode or turn off if appropriate
        if in_deadband:
            if current_mode in (HVACMode.HEAT, HVACMode.COOL):
                # Temperature reached target, can turn off
                return HVACMode.OFF, f"In deadband (error={temp_error:.1f}°C), turning off"
            else:
                # Already off or in other mode
                return current_mode, f"In deadband (error={temp_error:.1f}°C), staying {current_mode.value}"

        # Determine what we need based on temperature error
        needs_cooling = temp_error > context.deadband
        needs_heating = temp_error < -context.deadband

        # Get long-term dynamics for effectiveness check
        long_term_rate = context.long_term_rate

        # SMART SWITCHING LOGIC

        # Case 1: Currently COOLING but need heating
        if current_mode == HVACMode.COOL and needs_heating:
            if not context.device_capabilities.can_heat:
                return HVACMode.COOL, "Need heating but device cannot heat, staying in COOL"

            # Check if heating need is small
            if abs(temp_error) < 1.0:
                # Small heating need

                # Check outdoor temperature
                if outdoor_temp.value > 20:
                    # Outdoor is warm, house will naturally warm up
                    # Try setpoint correction first
                    return HVACMode.COOL, \
                           f"Small heating need ({temp_error:.1f}°C), outdoor warm ({outdoor_temp.value:.1f}°C), " \
                           "trying setpoint adjustment before mode switch"

            # Large heating need OR setpoint correction not appropriate
            # Check if cooling is ineffective (long-term dynamics show we're not cooling)
            if long_term_rate is not None and long_term_rate > -0.2:
                # Not cooling effectively, switch to heat
                return HVACMode.HEAT, \
                       f"Cooling ineffective (rate={long_term_rate:.1f}°C/h), switching to HEAT"

            # Switch to heating
            return HVACMode.HEAT, f"Heating needed (error={temp_error:.1f}°C), switching to HEAT"

        # Case 2: Currently HEATING but need cooling
        elif current_mode == HVACMode.HEAT and needs_cooling:
            if not context.device_capabilities.can_cool:
                return HVACMode.HEAT, "Need cooling but device cannot cool, staying in HEAT"

            # Check if cooling need is small
            if abs(temp_error) < 1.0:
                # Small cooling need

                # Check outdoor temperature
                if outdoor_temp.value < 15:
                    # Outdoor is cold, house will naturally cool down
                    # Try setpoint correction first
                    return HVACMode.HEAT, \
                           f"Small cooling need (+{temp_error:.1f}°C), outdoor cold ({outdoor_temp.value:.1f}°C), " \
                           "trying setpoint adjustment before mode switch"

            # Large cooling need OR setpoint correction not appropriate
            # Check if heating is ineffective (long-term dynamics show we're not heating)
            if long_term_rate is not None and long_term_rate < 0.2:
                # Not heating effectively, switch to cool
                return HVACMode.COOL, \
                       f"Heating ineffective (rate={long_term_rate:.1f}°C/h), switching to COOL"

            # Switch to cooling
            return HVACMode.COOL, f"Cooling needed (error={temp_error:.1f}°C), switching to COOL"

        # Case 3: Currently OFF, need to turn on
        elif current_mode == HVACMode.OFF:
            if needs_cooling:
                if not context.device_capabilities.can_cool:
                    return HVACMode.OFF, "Need cooling but device cannot cool"
                return HVACMode.COOL, f"Cooling needed (error={temp_error:.1f}°C), turning on COOL"

            elif needs_heating:
                if not context.device_capabilities.can_heat:
                    return HVACMode.OFF, "Need heating but device cannot heat"
                return HVACMode.HEAT, f"Heating needed (error={temp_error:.1f}°C), turning on HEAT"

        # Case 4: Already in correct mode (COOL and need cooling, or HEAT and need heating)
        elif current_mode == HVACMode.COOL and needs_cooling:
            return HVACMode.COOL, f"Continue cooling (error={temp_error:.1f}°C)"

        elif current_mode == HVACMode.HEAT and needs_heating:
            return HVACMode.HEAT, f"Continue heating (error={temp_error:.1f}°C)"

        # Fallback: keep current mode
        _LOGGER.debug(
            "Mode selection fallback: current=%s, error=%.1f, needs_cooling=%s, needs_heating=%s",
            current_mode.value,
            temp_error,
            needs_cooling,
            needs_heating,
        )
        return current_mode, "No mode change needed"

    def _can_switch_mode(self, context: ControlContext) -> bool:
        """Check if enough time has passed since last mode switch."""
        if context.last_mode_change is None:
            return True

        elapsed = (context.now - context.last_mode_change).total_seconds()
        return elapsed >= context.min_mode_switch_interval


# Keep old class name for backward compatibility during migration
OutdoorAwareModeSelectionPolicy = IntelligentModeSelectionPolicy
