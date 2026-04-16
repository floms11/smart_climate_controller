"""Multi-split system coordinator service."""
import logging
from typing import Optional
from datetime import datetime

from ..models import MultiSplitGroup
from ..value_objects import ControlContext, HVACMode

_LOGGER = logging.getLogger(__name__)


class MultiSplitModeSelector:
    """
    Selects optimal HVAC mode for multi-split group based on all zones' needs.

    Strategy:
    1. Collect mode preferences from all zones in the group
    2. Apply voting logic with priority rules:
       - Safety: Prevent too cold rooms in winter (heating priority)
       - Comfort: Maximize number of satisfied zones
       - Efficiency: Prefer mode that outdoor conditions favor
    3. Apply hysteresis to prevent frequent mode switching
    """

    def select_group_mode(
        self,
        group: MultiSplitGroup,
        zone_contexts: dict[str, ControlContext],
        zone_desired_modes: dict[str, HVACMode],
        outdoor_temp: float,
        outdoor_heat_threshold: float,
        outdoor_cool_threshold: float,
        now: datetime,
    ) -> tuple[HVACMode, str]:
        """
        Select optimal mode for the entire multi-split group.

        Args:
            group: Multi-split group configuration
            zone_contexts: Control contexts for each zone in the group
            zone_desired_modes: Desired modes for each zone (if operating independently)
            outdoor_temp: Current outdoor temperature
            outdoor_heat_threshold: Temperature below which heating is favored
            outdoor_cool_threshold: Temperature above which cooling is favored
            now: Current timestamp

        Returns:
            Tuple of (selected_mode, reason)
        """
        # Count votes for each mode
        heat_votes = 0
        cool_votes = 0
        heat_urgency = 0.0
        cool_urgency = 0.0

        for zone_id in group.zone_ids:
            if zone_id not in zone_contexts or zone_id not in zone_desired_modes:
                continue

            context = zone_contexts[zone_id]
            desired_mode = zone_desired_modes[zone_id]

            # Calculate temperature error (how far from target)
            temp_error = context.sensor_snapshot.room_temp.value - context.target_temp.value

            if desired_mode == HVACMode.HEAT:
                heat_votes += 1
                # Negative error means room is colder than target (more urgent)
                heat_urgency += abs(min(0, temp_error))
            elif desired_mode == HVACMode.COOL:
                cool_votes += 1
                # Positive error means room is hotter than target (more urgent)
                cool_urgency += max(0, temp_error)

        # Rule 1: Safety - prevent too cold rooms (heating takes priority in winter)
        if heat_votes > 0 and outdoor_temp < outdoor_heat_threshold:
            # If any zone needs heating and it's cold outside, prioritize heating
            if heat_urgency > cool_urgency * 1.5:  # 1.5x weight for heating in winter
                return HVACMode.HEAT, (
                    f"Heating priority: {heat_votes} zones need heat "
                    f"(urgency: {heat_urgency:.1f}°C), outdoor cold ({outdoor_temp:.1f}°C)"
                )

        # Rule 2: Safety - prevent overheating in summer
        if cool_votes > 0 and outdoor_temp > outdoor_cool_threshold:
            # If any zone needs cooling and it's hot outside, prioritize cooling
            if cool_urgency > heat_urgency * 1.5:  # 1.5x weight for cooling in summer
                return HVACMode.COOL, (
                    f"Cooling priority: {cool_votes} zones need cool "
                    f"(urgency: {cool_urgency:.1f}°C), outdoor hot ({outdoor_temp:.1f}°C)"
                )

        # Rule 3: Majority vote with urgency weighting
        if heat_votes > cool_votes:
            return HVACMode.HEAT, (
                f"Majority vote: {heat_votes} zones need heat vs {cool_votes} for cooling "
                f"(urgency H:{heat_urgency:.1f} C:{cool_urgency:.1f})"
            )
        elif cool_votes > heat_votes:
            return HVACMode.COOL, (
                f"Majority vote: {cool_votes} zones need cooling vs {heat_votes} for heat "
                f"(urgency H:{heat_urgency:.1f} C:{cool_urgency:.1f})"
            )

        # Rule 4: Tie-breaker - use urgency
        if heat_urgency > cool_urgency:
            return HVACMode.HEAT, (
                f"Tie-breaker by urgency: heat urgency {heat_urgency:.1f}°C > "
                f"cool urgency {cool_urgency:.1f}°C"
            )
        elif cool_urgency > heat_urgency:
            return HVACMode.COOL, (
                f"Tie-breaker by urgency: cool urgency {cool_urgency:.1f}°C > "
                f"heat urgency {heat_urgency:.1f}°C"
            )

        # Rule 5: Ultimate tie-breaker - outdoor conditions
        if outdoor_temp < outdoor_heat_threshold:
            return HVACMode.HEAT, f"Outdoor favors heating ({outdoor_temp:.1f}°C)"
        elif outdoor_temp > outdoor_cool_threshold:
            return HVACMode.COOL, f"Outdoor favors cooling ({outdoor_temp:.1f}°C)"

        # Rule 6: Preserve current mode if everything is neutral
        if group.current_shared_mode in (HVACMode.HEAT, HVACMode.COOL):
            return group.current_shared_mode, "All zones satisfied, preserving current mode"

        # Default fallback
        return HVACMode.HEAT, "Default mode selection"

    def should_change_group_mode(
        self,
        group: MultiSplitGroup,
        new_mode: HVACMode,
        min_mode_switch_interval: int,
        now: datetime,
    ) -> tuple[bool, str]:
        """
        Determine if group mode should be changed.

        Args:
            group: Multi-split group
            new_mode: Proposed new mode
            min_mode_switch_interval: Minimum seconds between mode changes
            now: Current timestamp

        Returns:
            Tuple of (should_change, reason)
        """
        # No change needed if mode is the same
        if group.current_shared_mode == new_mode:
            return False, "Mode unchanged"

        # Check if mode switch interval has elapsed
        if not group.can_change_mode(min_mode_switch_interval, now):
            elapsed = (now - group.last_mode_change).total_seconds()
            remaining = min_mode_switch_interval - elapsed
            return False, (
                f"Mode switch interval not elapsed "
                f"({remaining:.0f}s remaining of {min_mode_switch_interval}s)"
            )

        return True, f"Mode change from {group.current_shared_mode} to {new_mode}"

    def get_zone_action(
        self,
        zone_desired_mode: HVACMode,
        group_shared_mode: HVACMode,
        zone_context: ControlContext,
    ) -> tuple[HVACMode, str]:
        """
        Determine action for a specific zone within multi-split constraints.

        Args:
            zone_desired_mode: Mode this zone would prefer independently
            group_shared_mode: The shared mode all zones must use
            zone_context: Control context for this zone

        Returns:
            Tuple of (actual_mode, reason)
        """
        # If zone wants the same mode as group, allow it
        if zone_desired_mode == group_shared_mode:
            return group_shared_mode, f"Zone aligned with group mode {group_shared_mode.value}"

        # If zone wants OFF, allow it
        if zone_desired_mode == HVACMode.OFF:
            return HVACMode.OFF, "Zone can be turned off independently"

        # Calculate temperature error
        temp_error = (
            zone_context.sensor_snapshot.room_temp.value -
            zone_context.target_temp.value
        )

        # Zone wants different mode than group - must decide to run or turn off
        if group_shared_mode == HVACMode.HEAT:
            if temp_error > zone_context.deadband * 2:
                # Room is too hot and group is heating - turn off this zone
                return HVACMode.OFF, (
                    f"Zone too hot ({temp_error:+.1f}°C) but group heating - turning off"
                )
            else:
                # Room slightly warm but acceptable - run with group
                return HVACMode.HEAT, (
                    f"Zone prefers cooling but group heating - acceptable deviation ({temp_error:+.1f}°C)"
                )
        else:  # group_shared_mode == HVACMode.COOL
            if temp_error < -zone_context.deadband * 2:
                # Room is too cold and group is cooling - turn off this zone
                return HVACMode.OFF, (
                    f"Zone too cold ({temp_error:+.1f}°C) but group cooling - turning off"
                )
            else:
                # Room slightly cool but acceptable - run with group
                return HVACMode.COOL, (
                    f"Zone prefers heating but group cooling - acceptable deviation ({temp_error:+.1f}°C)"
                )
