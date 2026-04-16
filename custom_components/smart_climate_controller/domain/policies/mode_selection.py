"""Mode selection policy implementation."""
import logging
from typing import Optional

from .base import ModeSelectionPolicy
from ..value_objects import HVACMode, ControlContext, Temperature

_LOGGER = logging.getLogger(__name__)


class OutdoorAwareModeSelectionPolicy(ModeSelectionPolicy):
    """
    Selects HVAC mode based on indoor deviation and outdoor temperature.

    Key principles:
    - Use outdoor temperature to determine heating/cooling appropriateness
    - Implement hysteresis to prevent oscillation
    - Respect minimum mode switch intervals
    - Preserve current mode in neutral zones
    - Only switch to OFF in exceptional cases
    """

    def select_mode(
        self,
        current_mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        outdoor_temp: Temperature,
        context: ControlContext,
    ) -> tuple[HVACMode, str]:
        """Select HVAC mode with outdoor awareness and anti-oscillation."""

        # Check if controller is disabled
        if not context.controller_enabled:
            return HVACMode.OFF, "Controller disabled"

        # Check for manual mode override (highest priority after controller enabled check)
        if context.manual_mode_override:
            _LOGGER.info("Manual mode override active: %s", context.manual_mode_override)
            if context.manual_mode_override == "heat":
                if not context.device_capabilities.can_heat:
                    _LOGGER.warning("Manual HEAT mode requested but device cannot heat")
                    return current_mode, "Manual HEAT mode requested but device cannot heat"
                _LOGGER.info("Manual mode override: selecting HEAT")
                return HVACMode.HEAT, "Manual mode override: HEAT"
            elif context.manual_mode_override == "cool":
                if not context.device_capabilities.can_cool:
                    _LOGGER.warning("Manual COOL mode requested but device cannot cool")
                    return current_mode, "Manual COOL mode requested but device cannot cool"
                _LOGGER.info("Manual mode override: selecting COOL")
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

        # Check if in deadband - stabilization zone
        in_deadband = abs(temp_error) <= context.deadband

        # Determine temperature-based need
        needs_cooling = temp_error > context.deadband
        needs_heating = temp_error < -context.deadband

        # Check outdoor temperature zones with hysteresis
        outdoor_favors_heating = outdoor_temp.value < context.outdoor_heat_threshold
        outdoor_favors_cooling = outdoor_temp.value > context.outdoor_cool_threshold
        outdoor_neutral = not outdoor_favors_heating and not outdoor_favors_cooling

        # Apply hysteresis for outdoor decision
        if current_mode == HVACMode.HEAT:
            # When heating, use upper threshold + hysteresis for switching away
            outdoor_forbids_heating = outdoor_temp.value > (
                context.outdoor_cool_threshold + context.mode_switch_hysteresis
            )
            outdoor_forbids_cooling = outdoor_temp.value < (
                context.outdoor_heat_threshold - context.mode_switch_hysteresis
            )
        elif current_mode == HVACMode.COOL:
            # When cooling, use lower threshold - hysteresis for switching away
            outdoor_forbids_heating = outdoor_temp.value > (
                context.outdoor_cool_threshold + context.mode_switch_hysteresis
            )
            outdoor_forbids_cooling = outdoor_temp.value < (
                context.outdoor_heat_threshold - context.mode_switch_hysteresis
            )
        else:
            outdoor_forbids_heating = False
            outdoor_forbids_cooling = False

        # Case 1: In deadband - preserve current mode if reasonable
        if in_deadband:
            if current_mode in (HVACMode.HEAT, HVACMode.COOL):
                # Check if current mode is still appropriate for outdoor conditions
                if current_mode == HVACMode.HEAT and outdoor_forbids_heating:
                    return HVACMode.COOL, "Deadband but outdoor too warm for heating"
                if current_mode == HVACMode.COOL and outdoor_forbids_cooling:
                    return HVACMode.HEAT, "Deadband but outdoor too cold for cooling"

                return current_mode, f"In deadband, preserving {current_mode.value}"
            else:
                # Device was off or in other mode, decide based on outdoor
                if outdoor_favors_heating:
                    return HVACMode.HEAT, "Deadband, outdoor cold, selecting heat"
                elif outdoor_favors_cooling:
                    return HVACMode.COOL, "Deadband, outdoor warm, selecting cool"
                else:
                    # Neutral outdoor - pick based on slight deviation or keep current
                    if temp_error > 0:
                        return HVACMode.COOL, "Deadband, neutral outdoor, slight warm"
                    elif temp_error < 0:
                        return HVACMode.HEAT, "Deadband, neutral outdoor, slight cool"
                    else:
                        return current_mode, "Deadband, perfectly on target"

        # Case 2: Need cooling
        if needs_cooling:
            if not context.device_capabilities.can_cool:
                return current_mode, "Needs cooling but device cannot cool"

            # Check outdoor compatibility
            if outdoor_forbids_cooling:
                _LOGGER.warning(
                    "Room needs cooling but outdoor is too cold (%.1f°C). "
                    "Consider checking for heat sources or insulation.",
                    outdoor_temp.value
                )
                # Still allow cooling if temperature is significantly high
                if temp_error > context.deadband * 2:
                    return HVACMode.COOL, f"Force cooling despite cold outdoor (error={temp_error:.1f})"
                else:
                    return current_mode, "Needs cooling but outdoor forbids"

            return HVACMode.COOL, f"Cooling needed (error={temp_error:.1f}°C)"

        # Case 3: Need heating
        if needs_heating:
            if not context.device_capabilities.can_heat:
                return current_mode, "Needs heating but device cannot heat"

            # Check outdoor compatibility
            if outdoor_forbids_heating:
                _LOGGER.warning(
                    "Room needs heating but outdoor is too warm (%.1f°C). "
                    "Consider checking for cold sources or insulation.",
                    outdoor_temp.value
                )
                # Still allow heating if temperature is significantly low
                if temp_error < -context.deadband * 2:
                    return HVACMode.HEAT, f"Force heating despite warm outdoor (error={temp_error:.1f})"
                else:
                    return current_mode, "Needs heating but outdoor forbids"

            return HVACMode.HEAT, f"Heating needed (error={temp_error:.1f}°C)"

        # Fallback - should not reach here
        return current_mode, "No mode change needed"

    def _can_switch_mode(self, context: ControlContext) -> bool:
        """Check if enough time has passed since last mode switch."""
        if context.last_mode_change is None:
            return True

        elapsed = (context.now - context.last_mode_change).total_seconds()
        return elapsed >= context.min_mode_switch_interval
