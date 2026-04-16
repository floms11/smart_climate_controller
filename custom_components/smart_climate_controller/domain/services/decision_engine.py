"""Core decision engine for climate control."""
import logging
from typing import Optional

from ..value_objects import (
    ControlContext,
    ControlDecision,
    DecisionType,
    HVACMode,
    Temperature,
)
from ..policies.base import (
    ModeSelectionPolicy,
    SetpointAdjustmentPolicy,
    SafetyPolicy,
)

_LOGGER = logging.getLogger(__name__)


class ClimateDecisionEngine:
    """
    Core decision engine - orchestrates policies to make control decisions.

    This is the brain of the system. It:
    1. Checks safety conditions
    2. Determines desired HVAC mode
    3. Calculates optimal setpoint
    4. Decides if commands should be sent
    5. Respects timing constraints
    """

    def __init__(
        self,
        mode_selection_policy: ModeSelectionPolicy,
        setpoint_policy: SetpointAdjustmentPolicy,
        safety_policy: SafetyPolicy,
    ):
        """Initialize decision engine with policies."""
        self.mode_selection_policy = mode_selection_policy
        self.setpoint_policy = setpoint_policy
        self.safety_policy = safety_policy

    def make_decision(self, context: ControlContext) -> ControlDecision:
        """
        Make a control decision based on current context.

        Returns complete decision including what to do and why.
        """
        _LOGGER.debug(
            "Making decision: room=%.1f°C, target=%.1f°C, outdoor=%.1f°C, mode=%s",
            context.sensor_snapshot.room_temperature.value,
            context.target_temperature.value,
            context.sensor_snapshot.outdoor_temperature.value,
            context.device_state.hvac_mode.value,
        )

        # Step 1: Safety check
        should_stop, safety_reason = self.safety_policy.should_emergency_stop(context)
        if should_stop:
            _LOGGER.warning("Safety stop triggered: %s", safety_reason)
            return ControlDecision(
                decision_type=DecisionType.TURN_OFF,
                desired_mode=HVACMode.OFF,
                desired_setpoint=None,
                reason=f"SAFETY: {safety_reason}",
                should_send_command=self._should_send_command(context, HVACMode.OFF, None),
                timestamp=context.now,
            )

        # Step 2: Check if controller is enabled
        if not context.controller_enabled:
            return ControlDecision(
                decision_type=DecisionType.TURN_OFF,
                desired_mode=HVACMode.OFF,
                desired_setpoint=None,
                reason="Controller disabled",
                should_send_command=self._should_send_command(context, HVACMode.OFF, None),
                timestamp=context.now,
            )

        # Step 3: Select desired mode
        current_mode = context.device_state.hvac_mode
        desired_mode, mode_reason = self.mode_selection_policy.select_mode(
            current_mode=current_mode,
            room_temp=context.sensor_snapshot.room_temperature,
            target_temp=context.target_temperature,
            outdoor_temp=context.sensor_snapshot.outdoor_temperature,
            context=context,
        )

        # Step 4: Calculate desired setpoint
        temp_rate = (
            context.sensor_snapshot.temperature_rate.degrees_per_hour
            if context.sensor_snapshot.temperature_rate
            else None
        )

        desired_setpoint, setpoint_reason = self.setpoint_policy.calculate_setpoint(
            mode=desired_mode,
            room_temp=context.sensor_snapshot.room_temperature,
            target_temp=context.target_temperature,
            temp_rate=temp_rate,
            context=context,
        )

        # Step 5: Determine decision type
        mode_changed = desired_mode != current_mode
        setpoint_changed = self._setpoint_changed(
            context.device_state.current_setpoint,
            desired_setpoint,
        )

        if desired_mode == HVACMode.OFF:
            decision_type = DecisionType.TURN_OFF
        elif mode_changed and setpoint_changed:
            decision_type = DecisionType.SET_MODE_AND_SETPOINT
        elif mode_changed:
            decision_type = DecisionType.SET_MODE
        elif setpoint_changed:
            decision_type = DecisionType.SET_SETPOINT
        else:
            decision_type = DecisionType.NO_ACTION

        # Step 6: Build comprehensive reason
        reason_parts = [mode_reason]
        if desired_mode != HVACMode.OFF:
            reason_parts.append(setpoint_reason)

        reason = " | ".join(reason_parts)

        # Step 7: Anti-flapping checks
        # Check if we can turn off (respect min_run_time)
        if desired_mode == HVACMode.OFF and current_mode in (HVACMode.HEAT, HVACMode.COOL):
            can_turn_off, run_time_reason = self._can_turn_off(context)
            if not can_turn_off:
                # Keep current mode running
                return ControlDecision(
                    decision_type=DecisionType.NO_ACTION,
                    desired_mode=current_mode,
                    desired_setpoint=context.device_state.current_setpoint,
                    reason=f"Want to turn off but: {run_time_reason}",
                    should_send_command=False,
                    timestamp=context.now,
                )

        # Check if we can turn on (respect min_idle_time)
        if desired_mode in (HVACMode.HEAT, HVACMode.COOL) and current_mode == HVACMode.OFF:
            can_turn_on, idle_time_reason = self._can_turn_on(context)
            if not can_turn_on:
                # Stay off
                return ControlDecision(
                    decision_type=DecisionType.NO_ACTION,
                    desired_mode=HVACMode.OFF,
                    desired_setpoint=None,
                    reason=f"Want to turn on but: {idle_time_reason}",
                    should_send_command=False,
                    timestamp=context.now,
                )

        # Step 8: Determine if command should be sent
        should_send = self._should_send_command(
            context,
            desired_mode,
            desired_setpoint if desired_mode != HVACMode.OFF else None,
        )

        decision = ControlDecision(
            decision_type=decision_type,
            desired_mode=desired_mode,
            desired_setpoint=desired_setpoint if desired_mode != HVACMode.OFF else None,
            reason=reason,
            should_send_command=should_send,
            timestamp=context.now,
        )

        _LOGGER.info(
            "Decision: %s | Mode: %s -> %s | Setpoint: %s -> %s | Send: %s | Reason: %s",
            decision_type.value,
            current_mode.value,
            desired_mode.value,
            f"{context.device_state.current_setpoint.value:.1f}" if context.device_state.current_setpoint else "N/A",
            f"{desired_setpoint.value:.1f}" if desired_setpoint else "N/A",
            should_send,
            reason,
        )

        return decision

    def _can_turn_off(self, context: ControlContext) -> tuple[bool, str]:
        """
        Check if AC can be turned off (respecting min_run_time).

        Returns:
            Tuple of (can_turn_off, reason)
        """
        if context.last_run_start is None:
            return True, "No run time restriction"

        elapsed = (context.now - context.last_run_start).total_seconds()
        if elapsed < context.min_run_time:
            remaining = context.min_run_time - elapsed
            return False, f"Min run time not met, {remaining:.0f}s remaining"

        return True, "Min run time satisfied"

    def _can_turn_on(self, context: ControlContext) -> tuple[bool, str]:
        """
        Check if AC can be turned on (respecting min_idle_time).

        Returns:
            Tuple of (can_turn_on, reason)
        """
        if context.last_idle_start is None:
            return True, "No idle time restriction"

        elapsed = (context.now - context.last_idle_start).total_seconds()
        if elapsed < context.min_idle_time:
            remaining = context.min_idle_time - elapsed
            return False, f"Min idle time not met, {remaining:.0f}s remaining"

        return True, "Min idle time satisfied"

    def _setpoint_changed(
        self,
        current: Optional[Temperature],
        desired: Temperature,
        threshold: float = 0.3,
    ) -> bool:
        """Check if setpoint has changed significantly."""
        if current is None:
            return True
        return abs(current.value - desired.value) > threshold

    def _should_send_command(
        self,
        context: ControlContext,
        desired_mode: HVACMode,
        desired_setpoint: Optional[Temperature],
    ) -> bool:
        """
        Determine if command should actually be sent to device.

        Prevents:
        - Sending same command repeatedly
        - Sending commands too frequently
        """
        current_state = context.device_state

        _LOGGER.debug(
            "Checking if should send command: desired_mode=%s, current_mode=%s, desired_setpoint=%s, current_setpoint=%s",
            desired_mode.value,
            current_state.hvac_mode.value,
            desired_setpoint.value if desired_setpoint else None,
            current_state.current_setpoint.value if current_state.current_setpoint else None,
        )

        # Check command interval timing
        if context.last_command_sent is not None:
            elapsed = (context.now - context.last_command_sent).total_seconds()
            if elapsed < context.min_command_interval:
                _LOGGER.debug(
                    "Command throttled: only %.0fs since last command (min: %ds)",
                    elapsed,
                    context.min_command_interval,
                )
                return False

        # If mode is different, send command
        if desired_mode != current_state.hvac_mode:
            _LOGGER.debug("Mode changed: %s -> %s, will send command", current_state.hvac_mode.value, desired_mode.value)
            return True

        # If turning off, and already off, don't send
        if desired_mode == HVACMode.OFF and current_state.hvac_mode == HVACMode.OFF:
            _LOGGER.debug("Already OFF, no command needed")
            return False

        # If setpoint changed significantly, send command
        if desired_setpoint is not None and self._setpoint_changed(
            current_state.current_setpoint,
            desired_setpoint,
        ):
            _LOGGER.debug("Setpoint changed significantly, will send command")
            return True

        # No meaningful change
        _LOGGER.debug("No meaningful change, no command needed")
        return False
