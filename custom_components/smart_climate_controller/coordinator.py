"""Coordinator for Smart Climate Controller."""
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AC_NAME,
    CONF_AC_UNITS,
    CONF_BOOST_DURATION,
    CONF_BOOST_TEMP_OFFSET,
    CONF_CLIMATE_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_MAJOR_CORRECTION_VALUE,
    CONF_MAJOR_DEVIATION_THRESHOLD,
    CONF_MIN_MODE_SWITCH_INTERVAL,
    CONF_MIN_POWER_SWITCH_INTERVAL,
    CONF_MINOR_CORRECTION_HYSTERESIS,
    CONF_MINOR_CORRECTION_VALUE,
    CONF_MODE_SWITCH_TEMP_THRESHOLD,
    CONF_OUTDOOR_TEMP_COOL_ONLY,
    CONF_OUTDOOR_TEMP_HEAT_ONLY,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_USE_LINEAR_CORRECTION,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMP_OFFSET,
    DEFAULT_MAJOR_CORRECTION_VALUE,
    DEFAULT_MAJOR_DEVIATION_THRESHOLD,
    DEFAULT_MIN_MODE_SWITCH_INTERVAL,
    DEFAULT_MIN_POWER_SWITCH_INTERVAL,
    DEFAULT_MINOR_CORRECTION_HYSTERESIS,
    DEFAULT_MINOR_CORRECTION_VALUE,
    DEFAULT_MODE_SWITCH_TEMP_THRESHOLD,
    DEFAULT_OUTDOOR_TEMP_COOL_ONLY,
    DEFAULT_OUTDOOR_TEMP_HEAT_ONLY,
    DEFAULT_USE_LINEAR_CORRECTION,
    PRESET_BOOST_COOL,
    PRESET_BOOST_HEAT,
    PRESET_COMFORT,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class RoomState:
    """State for a single room."""

    def __init__(self, room_name: str):
        """Initialize room state."""
        self.room_name = room_name
        self.target_temperature: float = 22.0  # Default temperature
        self.hvac_mode: HVACMode = HVACMode.OFF
        self.last_mode_switch: datetime | None = None
        self.last_power_switch: datetime | None = None
        self.last_physical_mode: HVACMode | None = None  # Track last physical mode (heat/cool)
        self.preset_mode: str = "comfort"  # Default preset
        self.boost_end_time: datetime | None = None  # When boost mode should end
        self.saved_temperature: float | None = None  # Temperature before boost
        self.saved_hvac_mode: HVACMode | None = None  # HVAC mode before boost


class SmartClimateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Smart Climate Controller logic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Smart Climate Controller",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._room_states: dict[str, RoomState] = {}
        self._climate_entities: dict[str, Any] = {}

        # Initialize room states - support both old and new formats
        # New format: CONF_AC_UNITS
        if CONF_AC_UNITS in self.entry.data:
            for ac_config in self.entry.data.get(CONF_AC_UNITS, []):
                ac_name = ac_config[CONF_AC_NAME]
                self._room_states[ac_name] = RoomState(ac_name)
        # Legacy format: CONF_ROOMS
        else:
            for room_config in self.entry.data.get(CONF_ROOMS, []):
                room_name = room_config[CONF_ROOM_NAME]
                self._room_states[room_name] = RoomState(room_name)

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and restore state."""
        await self._restore_state()
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self):
        """Update data via library."""
        try:
            # Check for expired boost modes
            now = dt_util.utcnow()
            for room_name, room_state in self._room_states.items():
                if room_state.boost_end_time and now >= room_state.boost_end_time:
                    _LOGGER.info(
                        "Thermostat %s: boost mode expired, restoring previous state",
                        room_name
                    )
                    await self._restore_from_boost(room_name)

            # Get all AC units (rooms) - they're all in one synchronized group
            ac_names = list(self._room_states.keys())

            if ac_names:
                # Process all ACs as one synchronized group
                await self._process_group("multi_split", ac_names)

            # Save state
            await self._save_state()

            return {}
        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}") from err

    async def async_shutdown(self):
        """Shutdown coordinator."""
        await self._save_state()

    def _get_room_config(self, room_name: str) -> dict[str, Any] | None:
        """Get room/AC configuration - supports both old and new formats."""
        config = None
        # New format: CONF_AC_UNITS
        if CONF_AC_UNITS in self.entry.data:
            for ac_config in self.entry.data.get(CONF_AC_UNITS, []):
                if ac_config[CONF_AC_NAME] == room_name:
                    config = ac_config.copy()
                    break
        # Legacy format: CONF_ROOMS
        else:
            for room_config in self.entry.data.get(CONF_ROOMS, []):
                if room_config[CONF_ROOM_NAME] == room_name:
                    config = room_config.copy()
                    break

        # Override outdoor sensor from options if available
        if config and CONF_OUTDOOR_TEMP_SENSOR in self.entry.options:
            config[CONF_OUTDOOR_TEMP_SENSOR] = self.entry.options[CONF_OUTDOOR_TEMP_SENSOR]

        return config

    def _get_global_option(self, key: str, default: Any) -> Any:
        """Get global option value."""
        return self.entry.options.get(key, default)

    async def _process_group(self, group_name: str, room_names: list[str]):
        """Process a multi-split group."""
        _LOGGER.info("▶ Processing group %s with rooms: %s", group_name, room_names)

        # Step 1: Determine group's actual HVAC mode based on thermostat modes
        group_hvac_mode = self._determine_group_hvac_mode(room_names)
        _LOGGER.info("Group %s: thermostat mode = %s", group_name, group_hvac_mode)

        if group_hvac_mode == HVACMode.OFF:
            # Turn off all ACs in the group
            _LOGGER.debug("Group %s is OFF, turning off all ACs", group_name)
            for room_name in room_names:
                await self._control_room_climate(room_name, HVACMode.OFF, None)
            return

        # Step 2: Determine physical mode (heat/cool) for the group
        physical_mode = await self._determine_physical_mode(
            group_name, room_names, group_hvac_mode
        )

        if physical_mode is None:
            # Cannot determine mode yet, keep off or maintain current
            _LOGGER.warning("Group %s: ✗ cannot determine physical mode", group_name)
            return

        _LOGGER.info("Group %s: physical mode = %s (will control ACs)", group_name, physical_mode)

        # Step 3: Check if physical mode changed for the group
        group_mode_changed = False
        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if room_state and room_state.hvac_mode != HVACMode.OFF:
                if room_state.last_physical_mode != physical_mode:
                    group_mode_changed = True
                    _LOGGER.info(
                        "Group %s: physical mode changed from %s to %s",
                        group_name, room_state.last_physical_mode, physical_mode
                    )
                    break

        # Step 4: If group mode changed, synchronize all ACs to new mode immediately
        if group_mode_changed:
            _LOGGER.info("Group %s: synchronizing all ACs to mode %s", group_name, physical_mode)
            for room_name in room_names:
                room_state = self._room_states.get(room_name)
                if not room_state or room_state.hvac_mode == HVACMode.OFF:
                    continue

                # Synchronize AC mode (bypass temperature logic, just set mode)
                room_config = self._get_room_config(room_name)
                if room_config:
                    climate_entity_id = room_config[CONF_CLIMATE_ENTITY]
                    climate_state = self.hass.states.get(climate_entity_id)
                    if climate_state:
                        current_mode = HVACMode(climate_state.state) if climate_state.state in HVACMode else None

                        # Only sync if AC mode doesn't match
                        if current_mode != physical_mode and current_mode != HVACMode.OFF:
                            _LOGGER.info(
                                "Room %s: syncing AC from %s to %s",
                                room_name, current_mode, physical_mode
                            )
                            # Force mode change by resetting timer
                            room_state.last_mode_switch = dt_util.utcnow()
                            await self._control_room_climate(room_name, physical_mode, room_state.target_temperature)

                        # Update tracked physical mode
                        room_state.last_physical_mode = physical_mode

        # Step 5: Control each room's temperature based on physical mode
        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if not room_state or room_state.hvac_mode == HVACMode.OFF:
                _LOGGER.debug("Room %s: skipping (state=%s, mode=%s)",
                             room_name, room_state, room_state.hvac_mode if room_state else None)
                continue

            # Check if physical mode changed for this room
            mode_changed = room_state.last_physical_mode != physical_mode

            _LOGGER.debug("Room %s: controlling temperature (physical_mode=%s, target=%.1f, mode_changed=%s)",
                         room_name, physical_mode, room_state.target_temperature, mode_changed)
            await self._control_room_temperature(room_name, physical_mode, mode_changed)

            # Update last physical mode
            room_state.last_physical_mode = physical_mode

    def _determine_group_hvac_mode(self, room_names: list[str]) -> HVACMode:
        """Determine group HVAC mode based on thermostat modes.

        This implements thermostat synchronization logic:
        - If any thermostat switches to heat/cool/auto, all active thermostats in group switch to that mode
        - Returns the most recent non-off mode, or OFF if all are off
        """
        most_recent_mode = HVACMode.OFF
        most_recent_time = None

        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if not room_state:
                continue

            if room_state.hvac_mode == HVACMode.OFF:
                continue

            # Check if this is the most recent mode change
            if most_recent_time is None or (
                room_state.last_mode_switch
                and room_state.last_mode_switch > most_recent_time
            ):
                most_recent_mode = room_state.hvac_mode
                most_recent_time = room_state.last_mode_switch

        return most_recent_mode

    async def _determine_physical_mode(
        self, group_name: str, room_names: list[str], group_hvac_mode: HVACMode
    ) -> HVACMode | None:
        """Determine physical mode (heat/cool) for ACs in the group.

        This implements the auto mode logic and outdoor temperature checks.
        """
        if group_hvac_mode == HVACMode.HEAT:
            return HVACMode.HEAT

        if group_hvac_mode == HVACMode.COOL:
            return HVACMode.COOL

        # group_hvac_mode is AUTO - check if any room is in boost mode
        # Boost mode forces a specific physical mode until boost ends
        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if room_state and room_state.preset_mode in (PRESET_BOOST_HEAT, PRESET_BOOST_COOL):
                forced_mode = room_state.last_physical_mode
                _LOGGER.info(
                    "Group %s: boost mode active in %s (preset=%s), forcing physical mode to %s",
                    group_name, room_name, room_state.preset_mode, forced_mode
                )
                return forced_mode

        # No boost mode active - need to determine physical mode normally
        # Get outdoor temperature (use first room's sensor)
        outdoor_temp = None
        for room_name in room_names:
            room_config = self._get_room_config(room_name)
            if room_config:
                outdoor_temp = self._get_sensor_temperature(
                    room_config[CONF_OUTDOOR_TEMP_SENSOR]
                )
                break

        if outdoor_temp is None:
            _LOGGER.warning("Cannot determine outdoor temperature for group %s", group_name)
            return None

        heat_only_threshold = self._get_global_option(
            CONF_OUTDOOR_TEMP_HEAT_ONLY, DEFAULT_OUTDOOR_TEMP_HEAT_ONLY
        )
        cool_only_threshold = self._get_global_option(
            CONF_OUTDOOR_TEMP_COOL_ONLY, DEFAULT_OUTDOOR_TEMP_COOL_ONLY
        )

        # Check temperature thresholds
        if outdoor_temp < heat_only_threshold:
            return HVACMode.HEAT

        if outdoor_temp > cool_only_threshold:
            return HVACMode.COOL

        # In transition zone - analyze room needs
        return await self._determine_mode_in_transition_zone(
            group_name, room_names, outdoor_temp
        )

    async def _determine_mode_in_transition_zone(
        self, group_name: str, room_names: list[str], outdoor_temp: float
    ) -> HVACMode | None:
        """Determine mode when outdoor temperature is in transition zone.

        Analyzes which rooms need heating/cooling and chooses the mode that serves
        the most critical needs while respecting minimum mode switch intervals.
        """
        # Check minimum mode switch interval
        min_interval = self._get_global_option(
            CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL
        )

        # Find the most recent mode switch in the group
        most_recent_switch = None
        current_physical_mode = None

        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if not room_state:
                continue

            if room_state.last_mode_switch:
                if most_recent_switch is None or room_state.last_mode_switch > most_recent_switch:
                    most_recent_switch = room_state.last_mode_switch
                    # Get current physical mode from AC
                    room_config = self._get_room_config(room_name)
                    if room_config:
                        climate_state = self.hass.states.get(room_config[CONF_CLIMATE_ENTITY])
                        if climate_state and climate_state.state in (HVACMode.HEAT, HVACMode.COOL):
                            current_physical_mode = HVACMode(climate_state.state)

        # If mode was switched recently, keep current mode
        if most_recent_switch and current_physical_mode:
            time_since_switch = (dt_util.utcnow() - most_recent_switch).total_seconds()
            if time_since_switch < min_interval:
                _LOGGER.debug(
                    "Group %s: keeping mode %s (switched %.0f sec ago, min %d sec)",
                    group_name, current_physical_mode, time_since_switch, min_interval
                )
                return current_physical_mode

        # Analyze room needs - only count significant deviations
        heat_need_score = 0
        cool_need_score = 0

        # Use mode switch temperature threshold for mode switching decisions
        mode_switch_threshold = self._get_global_option(
            CONF_MODE_SWITCH_TEMP_THRESHOLD, DEFAULT_MODE_SWITCH_TEMP_THRESHOLD
        )

        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            room_config = self._get_room_config(room_name)

            if not room_state or not room_config or room_state.hvac_mode == HVACMode.OFF:
                continue

            indoor_temp = self._get_sensor_temperature(room_config[CONF_INDOOR_TEMP_SENSOR])
            if indoor_temp is None:
                continue

            temp_diff = indoor_temp - room_state.target_temperature

            # Only count deviations greater than mode_switch_threshold to minimize mode switching
            if temp_diff < -mode_switch_threshold:
                heat_need_score += 10  # Need heating

            if temp_diff > mode_switch_threshold:
                cool_need_score += 10  # Need cooling

        # Decide based on scores
        if heat_need_score > cool_need_score:
            return HVACMode.HEAT
        elif cool_need_score > heat_need_score:
            return HVACMode.COOL
        elif current_physical_mode:
            # Equal needs - keep current mode
            return current_physical_mode
        else:
            # No clear need and no current mode - default to cool in transition zone
            return HVACMode.COOL

    async def _control_room_temperature(self, room_name: str, physical_mode: HVACMode, mode_changed: bool = False):
        """Control room temperature based on physical mode.

        Implements minor and major temperature correction logic.

        Args:
            room_name: Name of the room to control
            physical_mode: Physical HVAC mode (HEAT/COOL)
            mode_changed: True if physical mode just changed (e.g. heat -> cool)
        """
        room_state = self._room_states.get(room_name)
        room_config = self._get_room_config(room_name)

        if not room_state or not room_config:
            return

        indoor_temp = self._get_sensor_temperature(room_config[CONF_INDOOR_TEMP_SENSOR])
        if indoor_temp is None:
            _LOGGER.warning("Cannot get indoor temperature for room %s", room_name)
            return

        target_temp = room_state.target_temperature
        temp_diff = indoor_temp - target_temp

        # Get current AC state
        climate_entity_id = room_config[CONF_CLIMATE_ENTITY]
        climate_state = self.hass.states.get(climate_entity_id)
        current_mode = HVACMode(climate_state.state) if climate_state and climate_state.state in HVACMode else None
        is_currently_off = current_mode == HVACMode.OFF

        # Get configuration parameters
        minor_hysteresis = self._get_global_option(
            CONF_MINOR_CORRECTION_HYSTERESIS, DEFAULT_MINOR_CORRECTION_HYSTERESIS
        )
        minor_correction = self._get_global_option(
            CONF_MINOR_CORRECTION_VALUE, DEFAULT_MINOR_CORRECTION_VALUE
        )
        major_correction = self._get_global_option(
            CONF_MAJOR_CORRECTION_VALUE, DEFAULT_MAJOR_CORRECTION_VALUE
        )
        major_threshold = self._get_global_option(
            CONF_MAJOR_DEVIATION_THRESHOLD, DEFAULT_MAJOR_DEVIATION_THRESHOLD
        )

        # AC temperature limits (from climate entity attributes)
        AC_MIN_TEMP = 16.0
        AC_MAX_TEMP = 30.0

        ac_target_temp = None
        should_turn_off = False

        _LOGGER.info(
            "Room %s: temperature control - indoor=%.1f, target=%.1f, diff=%.1f, mode=%s, major_threshold=%.1f",
            room_name, indoor_temp, target_temp, temp_diff, physical_mode, major_threshold
        )

        if physical_mode == HVACMode.HEAT:
            # Heating mode logic
            if temp_diff > major_threshold:
                # Room is too hot (>1°C above target) - turn off AC
                should_turn_off = True
                _LOGGER.info(
                    "Room %s: 🔴 HEAT mode - room too hot (diff %.1f > %.1f) - TURNING OFF",
                    room_name, temp_diff, major_threshold
                )
            elif temp_diff < -major_threshold:
                # Room is very cold (<-1°C) - major correction
                ac_target_temp = min(target_temp + major_correction, AC_MAX_TEMP)
                _LOGGER.info(
                    "Room %s: HEAT mode - major correction: %.1f + %.1f = %.1f",
                    room_name, target_temp, major_correction, ac_target_temp
                )
            elif temp_diff < -minor_hysteresis or temp_diff > minor_hysteresis:
                # Room is beyond ±0.5°C range - major correction
                if temp_diff < -minor_hysteresis:
                    # Cold side: add major correction
                    ac_target_temp = min(target_temp + major_correction, AC_MAX_TEMP)
                    _LOGGER.info(
                        "Room %s: HEAT mode - major correction cold side: %.1f + %.1f = %.1f",
                        room_name, target_temp, major_correction, ac_target_temp
                    )
                else:
                    # Warm side: subtract major correction
                    ac_target_temp = max(target_temp - major_correction, AC_MIN_TEMP)
                    _LOGGER.info(
                        "Room %s: HEAT mode - major correction warm side: %.1f - %.1f = %.1f",
                        room_name, target_temp, major_correction, ac_target_temp
                    )
            else:
                # Within acceptable range (-0.5°C to +1°C)
                if mode_changed:
                    # Mode just changed - turn off ACs in acceptable range
                    should_turn_off = True
                    _LOGGER.info(
                        "Room %s: HEAT mode - within acceptable range (diff %.1f), mode changed - turning off",
                        room_name, temp_diff
                    )
                elif is_currently_off:
                    # AC is already OFF and temp in range - keep it off
                    _LOGGER.info(
                        "Room %s: HEAT mode - within acceptable range (diff %.1f), AC already OFF - keeping OFF",
                        room_name, temp_diff
                    )
                    return  # Don't send any commands
                else:
                    # AC is ON - check if linear correction is enabled
                    use_linear = self._get_global_option(
                        CONF_USE_LINEAR_CORRECTION, DEFAULT_USE_LINEAR_CORRECTION
                    )
                    if use_linear:
                        # Linear correction works only in ±minor_hysteresis range (±0.5°C)
                        # Beyond that, use major correction
                        if temp_diff < -minor_hysteresis or temp_diff > minor_hysteresis:
                            # Beyond ±0.5°C range - use major correction
                            if temp_diff < -minor_hysteresis:
                                # Cold side: beyond -0.5°C
                                ac_target_temp = min(target_temp + major_correction, AC_MAX_TEMP)
                                _LOGGER.info(
                                    "Room %s: HEAT mode - beyond linear range (diff %.1f < -%.1f): %.1f + %.1f = %.1f",
                                    room_name, temp_diff, minor_hysteresis, target_temp, major_correction, ac_target_temp
                                )
                            else:
                                # Warm side: beyond +0.5°C
                                ac_target_temp = max(target_temp - major_correction, AC_MIN_TEMP)
                                _LOGGER.info(
                                    "Room %s: HEAT mode - beyond linear range (diff %.1f > +%.1f): %.1f - %.1f = %.1f",
                                    room_name, temp_diff, minor_hysteresis, target_temp, major_correction, ac_target_temp
                                )
                        else:
                            # Within ±0.5°C range - linear correction
                            # At 0°C diff: no correction
                            # At ±0.5°C diff: full minor_correction
                            ratio = abs(temp_diff) / minor_hysteresis  # 0.0 to 1.0
                            if temp_diff < 0:
                                # Cold side: add correction
                                correction = ratio * minor_correction
                                ac_target_temp = min(target_temp + correction, AC_MAX_TEMP)
                                _LOGGER.info(
                                    "Room %s: HEAT mode - linear correction cold (diff %.1f, ratio %.2f): %.1f + %.1f = %.1f",
                                    room_name, temp_diff, ratio, target_temp, correction, ac_target_temp
                                )
                            else:
                                # Warm side: subtract correction
                                correction = ratio * minor_correction
                                ac_target_temp = max(target_temp - correction, AC_MIN_TEMP)
                                _LOGGER.info(
                                    "Room %s: HEAT mode - linear correction warm (diff %.1f, ratio %.2f): %.1f - %.1f = %.1f",
                                    room_name, temp_diff, ratio, target_temp, correction, ac_target_temp
                                )
                    else:
                        # No linear correction - maintain target temperature
                        ac_target_temp = target_temp
                        _LOGGER.info(
                            "Room %s: HEAT mode - within acceptable range (diff %.1f) - maintaining target %.1f",
                            room_name, temp_diff, ac_target_temp
                        )

        elif physical_mode == HVACMode.COOL:
            # Cooling mode logic
            if temp_diff < -major_threshold:
                # Room is too cold (<-1°C below target) - turn off AC
                should_turn_off = True
                _LOGGER.info(
                    "Room %s: 🔴 COOL mode - room too cold (diff %.1f < -%.1f) - TURNING OFF",
                    room_name, temp_diff, major_threshold
                )
            elif temp_diff > major_threshold:
                # Room is very hot (>1°C) - major correction
                ac_target_temp = max(target_temp - major_correction, AC_MIN_TEMP)
                _LOGGER.info(
                    "Room %s: COOL mode - major correction: %.1f - %.1f = %.1f",
                    room_name, target_temp, major_correction, ac_target_temp
                )
            elif temp_diff < -minor_hysteresis or temp_diff > minor_hysteresis:
                # Room is beyond ±0.5°C range - major correction
                if temp_diff > minor_hysteresis:
                    # Hot side: subtract major correction
                    ac_target_temp = max(target_temp - major_correction, AC_MIN_TEMP)
                    _LOGGER.info(
                        "Room %s: COOL mode - major correction hot side: %.1f - %.1f = %.1f",
                        room_name, target_temp, major_correction, ac_target_temp
                    )
                else:
                    # Cold side: add major correction
                    ac_target_temp = min(target_temp + major_correction, AC_MAX_TEMP)
                    _LOGGER.info(
                        "Room %s: COOL mode - major correction cold side: %.1f + %.1f = %.1f",
                        room_name, target_temp, major_correction, ac_target_temp
                    )
            else:
                # Within acceptable range (-1°C to +0.5°C)
                if mode_changed:
                    # Mode just changed - turn off ACs in acceptable range
                    should_turn_off = True
                    _LOGGER.info(
                        "Room %s: COOL mode - within acceptable range (diff %.1f), mode changed - turning off",
                        room_name, temp_diff
                    )
                elif is_currently_off:
                    # AC is already OFF and temp in range - keep it off
                    _LOGGER.info(
                        "Room %s: COOL mode - within acceptable range (diff %.1f), AC already OFF - keeping OFF",
                        room_name, temp_diff
                    )
                    return  # Don't send any commands
                else:
                    # AC is ON - check if linear correction is enabled
                    use_linear = self._get_global_option(
                        CONF_USE_LINEAR_CORRECTION, DEFAULT_USE_LINEAR_CORRECTION
                    )
                    if use_linear:
                        # Linear correction works only in ±minor_hysteresis range (±0.5°C)
                        # Beyond that, use major correction
                        if temp_diff < -minor_hysteresis or temp_diff > minor_hysteresis:
                            # Beyond ±0.5°C range - use major correction
                            if temp_diff < -minor_hysteresis:
                                # Cold side: beyond -0.5°C
                                ac_target_temp = min(target_temp + major_correction, AC_MAX_TEMP)
                                _LOGGER.info(
                                    "Room %s: COOL mode - beyond linear range (diff %.1f < -%.1f): %.1f + %.1f = %.1f",
                                    room_name, temp_diff, minor_hysteresis, target_temp, major_correction, ac_target_temp
                                )
                            else:
                                # Hot side: beyond +0.5°C
                                ac_target_temp = max(target_temp - major_correction, AC_MIN_TEMP)
                                _LOGGER.info(
                                    "Room %s: COOL mode - beyond linear range (diff %.1f > +%.1f): %.1f - %.1f = %.1f",
                                    room_name, temp_diff, minor_hysteresis, target_temp, major_correction, ac_target_temp
                                )
                        else:
                            # Within ±0.5°C range - linear correction
                            # At 0°C diff: no correction
                            # At ±0.5°C diff: full minor_correction
                            ratio = abs(temp_diff) / minor_hysteresis  # 0.0 to 1.0
                            if temp_diff > 0:
                                # Hot side: subtract correction
                                correction = ratio * minor_correction
                                ac_target_temp = max(target_temp - correction, AC_MIN_TEMP)
                                _LOGGER.info(
                                    "Room %s: COOL mode - linear correction hot (diff %.1f, ratio %.2f): %.1f - %.1f = %.1f",
                                    room_name, temp_diff, ratio, target_temp, correction, ac_target_temp
                                )
                            else:
                                # Cold side: add correction
                                correction = ratio * minor_correction
                                ac_target_temp = min(target_temp + correction, AC_MAX_TEMP)
                                _LOGGER.info(
                                    "Room %s: COOL mode - linear correction cold (diff %.1f, ratio %.2f): %.1f + %.1f = %.1f",
                                    room_name, temp_diff, ratio, target_temp, correction, ac_target_temp
                                )
                    else:
                        # No linear correction - maintain target temperature
                        ac_target_temp = target_temp
                        _LOGGER.info(
                            "Room %s: COOL mode - within acceptable range (diff %.1f) - maintaining target %.1f",
                            room_name, temp_diff, ac_target_temp
                        )

        # Ensure temperature is within AC limits
        if ac_target_temp is not None:
            original_temp = ac_target_temp
            ac_target_temp = max(AC_MIN_TEMP, min(AC_MAX_TEMP, ac_target_temp))
            if original_temp != ac_target_temp:
                _LOGGER.warning(
                    "Room %s: clamped temperature from %.1f to %.1f (AC limits: %.1f-%.1f)",
                    room_name, original_temp, ac_target_temp, AC_MIN_TEMP, AC_MAX_TEMP
                )

        # Apply control
        if should_turn_off:
            _LOGGER.info("Room %s: >>> Calling _control_room_climate with mode=OFF", room_name)
            await self._control_room_climate(room_name, HVACMode.OFF, None)
        else:
            _LOGGER.info(
                "Room %s: >>> Calling _control_room_climate with mode=%s, temp=%.1f",
                room_name, physical_mode, ac_target_temp
            )
            await self._control_room_climate(room_name, physical_mode, ac_target_temp)

    async def _control_room_climate(
        self, room_name: str, hvac_mode: HVACMode, target_temperature: float | None
    ):
        """Control the physical climate entity for a room.

        Respects minimum power and mode switch intervals.
        """
        _LOGGER.info(
            "→ _control_room_climate called: room=%s, desired_mode=%s, desired_temp=%s",
            room_name, hvac_mode, target_temperature
        )

        room_config = self._get_room_config(room_name)
        room_state = self._room_states.get(room_name)

        if not room_config or not room_state:
            _LOGGER.warning("Room %s: config or state not found", room_name)
            return

        climate_entity_id = room_config[CONF_CLIMATE_ENTITY]
        climate_state = self.hass.states.get(climate_entity_id)

        if not climate_state:
            _LOGGER.warning("Climate entity %s not found", climate_entity_id)
            return

        current_mode = HVACMode(climate_state.state) if climate_state.state in HVACMode else None
        current_temp = climate_state.attributes.get("temperature")

        _LOGGER.info(
            "Room %s (%s): current state: mode=%s, temp=%s",
            room_name, climate_entity_id, current_mode, current_temp
        )

        # Check if we need to change anything
        mode_changed = hvac_mode != current_mode
        temp_changed = (
            target_temperature is not None
            and (current_temp is None or abs(target_temperature - current_temp) > 0.1)
        )

        if not mode_changed and not temp_changed:
            _LOGGER.info(
                "Room %s: ⊘ no changes needed (mode: %s=%s, temp: %s=%s)",
                room_name, hvac_mode, current_mode, target_temperature, current_temp
            )
            return

        _LOGGER.info(
            "Room %s: changes needed - mode_changed=%s, temp_changed=%s",
            room_name, mode_changed, temp_changed
        )

        # Check minimum intervals
        now = dt_util.utcnow()

        if mode_changed:
            # Check mode switch interval only for heat/cool/auto switching
            # Power on/off is controlled by min_power_switch_interval below
            if hvac_mode != HVACMode.OFF and current_mode != HVACMode.OFF:
                # Both old and new modes are active (heat/cool/auto) - check interval
                min_mode_interval = self._get_global_option(
                    CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL
                )

                if room_state.last_mode_switch:
                    time_since_switch = (now - room_state.last_mode_switch).total_seconds()
                    if time_since_switch < min_mode_interval:
                        _LOGGER.warning(
                            "Room %s: ⏱ BLOCKED mode change (%.0f sec since last, min %d sec required)",
                            room_name, time_since_switch, min_mode_interval
                        )
                        return
                    else:
                        _LOGGER.info(
                            "Room %s: mode switch interval OK (%.0f sec since last, min %d sec)",
                            room_name, time_since_switch, min_mode_interval
                        )
            else:
                _LOGGER.debug(
                    "Room %s: mode change involves OFF - will check power switch interval instead",
                    room_name
                )

        if (current_mode == HVACMode.OFF and hvac_mode != HVACMode.OFF) or (
            current_mode != HVACMode.OFF and hvac_mode == HVACMode.OFF
        ):
            # Check power switch interval
            min_power_interval = self._get_global_option(
                CONF_MIN_POWER_SWITCH_INTERVAL, DEFAULT_MIN_POWER_SWITCH_INTERVAL
            )

            if room_state.last_power_switch:
                time_since_switch = (now - room_state.last_power_switch).total_seconds()
                if time_since_switch < min_power_interval:
                    _LOGGER.warning(
                        "Room %s: ⏱ BLOCKED power change (%.0f sec since last, min %d sec required)",
                        room_name, time_since_switch, min_power_interval
                    )
                    return
                else:
                    _LOGGER.info(
                        "Room %s: power switch interval OK (%.0f sec since last, min %d sec)",
                        room_name, time_since_switch, min_power_interval
                    )

        # Apply changes
        _LOGGER.info(
            "Room %s: APPLYING CHANGES to %s - mode=%s, temp=%s (current: mode=%s, temp=%s)",
            room_name, climate_entity_id, hvac_mode, target_temperature, current_mode, current_temp
        )

        try:
            # Always change mode first if needed
            if mode_changed:
                _LOGGER.info(
                    "Room %s: calling climate.set_hvac_mode with entity_id=%s, hvac_mode=%s",
                    room_name, climate_entity_id, hvac_mode
                )
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {
                        "entity_id": climate_entity_id,
                        "hvac_mode": hvac_mode,
                    },
                    blocking=True,
                )
                room_state.last_mode_switch = now

                if (current_mode == HVACMode.OFF and hvac_mode != HVACMode.OFF) or (
                    current_mode != HVACMode.OFF and hvac_mode == HVACMode.OFF
                ):
                    room_state.last_power_switch = now

                _LOGGER.info("Room %s: ✓ Mode successfully changed to %s", room_name, hvac_mode)

            # Then set temperature if needed and AC is not OFF
            if temp_changed and hvac_mode != HVACMode.OFF and target_temperature is not None:
                _LOGGER.info(
                    "Room %s: calling climate.set_temperature with entity_id=%s, temperature=%s",
                    room_name, climate_entity_id, target_temperature
                )
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": climate_entity_id,
                        "temperature": target_temperature,
                    },
                    blocking=True,
                )
                _LOGGER.info("Room %s: ✓ Temperature successfully set to %s", room_name, target_temperature)

        except Exception as err:
            _LOGGER.error("Room %s: ✗ ERROR controlling climate %s: %s", room_name, climate_entity_id, err)

    def _get_sensor_temperature(self, entity_id: str) -> float | None:
        """Get temperature from sensor."""
        state = self.hass.states.get(entity_id)
        if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def set_room_hvac_mode(self, room_name: str, hvac_mode: HVACMode):
        """Set HVAC mode for a room's thermostat.

        This triggers synchronization for multi-split groups.
        """
        room_state = self._room_states.get(room_name)
        if not room_state:
            _LOGGER.warning("Room state not found for %s", room_name)
            return

        # Update room state
        old_mode = room_state.hvac_mode
        room_state.hvac_mode = hvac_mode
        room_state.last_mode_switch = dt_util.utcnow()

        _LOGGER.info(
            "Thermostat %s: mode changed from %s to %s",
            room_name, old_mode, hvac_mode
        )

        # Synchronize all ACs in the multi-split system
        _LOGGER.debug("Synchronizing all ACs after mode change in %s", room_name)
        await self._synchronize_all_modes(room_name, hvac_mode)

        # Save state immediately
        await self._save_state()

        # Notify all listeners that data has changed (updates UI)
        self.async_set_updated_data({})

        # Trigger processing to apply changes to physical ACs
        try:
            ac_names = list(self._room_states.keys())
            if ac_names:
                await self._process_group("multi_split", ac_names)
        except Exception as err:
            _LOGGER.error("Error processing ACs after mode change: %s", err)

    async def _synchronize_all_modes(
        self, initiating_room: str, new_mode: HVACMode
    ):
        """Synchronize thermostat modes across all ACs in the multi-split system.

        When one thermostat changes to heat/cool/auto, all other active
        thermostats should switch to the same mode.
        """
        if new_mode == HVACMode.OFF:
            # OFF mode doesn't trigger synchronization
            _LOGGER.debug("Skipping synchronization for OFF mode")
            return

        all_rooms = list(self._room_states.keys())
        _LOGGER.debug("All ACs: %s, initiating AC: %s", all_rooms, initiating_room)

        # Update other ACs
        synchronized_count = 0
        for room_name in all_rooms:
            if room_name == initiating_room:
                continue

            room_state = self._room_states.get(room_name)
            if not room_state:
                _LOGGER.warning("AC state not found for %s during synchronization", room_name)
                continue

            # Only synchronize if AC is not OFF
            if room_state.hvac_mode != HVACMode.OFF:
                old_mode = room_state.hvac_mode
                room_state.hvac_mode = new_mode
                room_state.last_mode_switch = dt_util.utcnow()
                synchronized_count += 1
                _LOGGER.info(
                    "Synchronized AC %s: %s -> %s",
                    room_name, old_mode, new_mode
                )
            else:
                _LOGGER.debug("Skipping AC %s: already OFF", room_name)

        _LOGGER.info("Synchronized %d ACs to mode %s", synchronized_count, new_mode)

    async def set_room_temperature(self, room_name: str, temperature: float):
        """Set target temperature for a room's thermostat."""
        room_state = self._room_states.get(room_name)
        if not room_state:
            _LOGGER.warning("Room state not found for %s", room_name)
            return

        old_temp = room_state.target_temperature
        room_state.target_temperature = temperature
        _LOGGER.info(
            "Thermostat %s: target temperature changed from %.1f to %.1f (mode: %s)",
            room_name, old_temp, temperature, room_state.hvac_mode
        )

        # Save state immediately
        await self._save_state()

        # Notify all listeners that data has changed (updates UI)
        self.async_set_updated_data({})

    async def set_room_preset_mode(self, room_name: str, preset_mode: str):
        """Set preset mode for a room's thermostat."""
        room_state = self._room_states.get(room_name)
        if not room_state:
            _LOGGER.warning("Room state not found for %s", room_name)
            return

        old_preset = room_state.preset_mode
        _LOGGER.info(
            "Thermostat %s: preset mode changing from %s to %s",
            room_name, old_preset, preset_mode
        )

        # Handle preset mode changes
        if preset_mode == PRESET_COMFORT:
            # Restore from boost if needed
            if old_preset in (PRESET_BOOST_HEAT, PRESET_BOOST_COOL):
                _LOGGER.info("Thermostat %s: manually restoring from boost mode", room_name)
                await self._restore_from_boost(room_name)
            else:
                room_state.preset_mode = PRESET_COMFORT

        elif preset_mode == PRESET_BOOST_HEAT:
            # Save current state before boost
            room_state.saved_temperature = room_state.target_temperature
            room_state.saved_hvac_mode = room_state.hvac_mode
            room_state.preset_mode = PRESET_BOOST_HEAT

            # Get current indoor temperature
            room_config = self._get_room_config(room_name)
            if room_config:
                indoor_temp = self._get_sensor_temperature(room_config[CONF_INDOOR_TEMP_SENSOR])
                if indoor_temp is not None:
                    # Set boost temperature
                    boost_offset = self._get_global_option(CONF_BOOST_TEMP_OFFSET, DEFAULT_BOOST_TEMP_OFFSET)
                    boost_temp = indoor_temp + boost_offset
                    room_state.target_temperature = max(16.0, min(30.0, boost_temp))

                    _LOGGER.info(
                        "Thermostat %s: BOOST HEAT - indoor=%.1f, offset=%.1f, new_target=%.1f",
                        room_name, indoor_temp, boost_offset, room_state.target_temperature
                    )

            # Keep thermostat in AUTO mode, but force physical mode to HEAT
            # This allows other thermostats to adapt while maintaining AUTO flexibility
            if room_state.hvac_mode != HVACMode.AUTO:
                room_state.hvac_mode = HVACMode.AUTO

            # Force physical mode to HEAT and reset mode switch timer
            room_state.last_mode_switch = dt_util.utcnow()  # Reset timer to allow immediate mode change
            room_state.last_physical_mode = HVACMode.HEAT

            # Set boost end time
            boost_duration = self._get_global_option(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)
            room_state.boost_end_time = dt_util.utcnow() + timedelta(seconds=boost_duration)

            _LOGGER.info(
                "Thermostat %s: boost will end at %s (in %d seconds, staying in AUTO with forced HEAT)",
                room_name, room_state.boost_end_time, boost_duration
            )

            # Immediately apply HEAT mode to AC (bypass temperature control logic)
            await self._control_room_climate(room_name, HVACMode.HEAT, room_state.target_temperature)

        elif preset_mode == PRESET_BOOST_COOL:
            # Save current state before boost
            room_state.saved_temperature = room_state.target_temperature
            room_state.saved_hvac_mode = room_state.hvac_mode
            room_state.preset_mode = PRESET_BOOST_COOL

            # Get current indoor temperature
            room_config = self._get_room_config(room_name)
            if room_config:
                indoor_temp = self._get_sensor_temperature(room_config[CONF_INDOOR_TEMP_SENSOR])
                if indoor_temp is not None:
                    # Set boost temperature
                    boost_offset = self._get_global_option(CONF_BOOST_TEMP_OFFSET, DEFAULT_BOOST_TEMP_OFFSET)
                    boost_temp = indoor_temp - boost_offset
                    room_state.target_temperature = max(16.0, min(30.0, boost_temp))

                    _LOGGER.info(
                        "Thermostat %s: BOOST COOL - indoor=%.1f, offset=%.1f, new_target=%.1f",
                        room_name, indoor_temp, boost_offset, room_state.target_temperature
                    )

            # Keep thermostat in AUTO mode, but force physical mode to COOL
            # This allows other thermostats to adapt while maintaining AUTO flexibility
            if room_state.hvac_mode != HVACMode.AUTO:
                room_state.hvac_mode = HVACMode.AUTO

            # Force physical mode to COOL and reset mode switch timer
            room_state.last_mode_switch = dt_util.utcnow()  # Reset timer to allow immediate mode change
            room_state.last_physical_mode = HVACMode.COOL

            # Set boost end time
            boost_duration = self._get_global_option(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)
            room_state.boost_end_time = dt_util.utcnow() + timedelta(seconds=boost_duration)

            _LOGGER.info(
                "Thermostat %s: boost will end at %s (in %d seconds, staying in AUTO with forced COOL)",
                room_name, room_state.boost_end_time, boost_duration
            )

            # Immediately apply COOL mode to AC (bypass temperature control logic)
            await self._control_room_climate(room_name, HVACMode.COOL, room_state.target_temperature)

        # Save state immediately
        await self._save_state()

        # Notify listeners that state has changed (updates UI)
        # Don't call async_request_refresh() here because we already applied
        # the mode change directly via _control_room_climate above
        self.async_set_updated_data({})

    async def _restore_from_boost(self, room_name: str):
        """Restore room state after boost mode ends."""
        room_state = self._room_states.get(room_name)
        if not room_state:
            return

        _LOGGER.info(
            "Thermostat %s: restoring from boost - saved_temp=%.1f, saved_mode=%s",
            room_name,
            room_state.saved_temperature if room_state.saved_temperature else 0,
            room_state.saved_hvac_mode
        )

        # Restore saved state
        if room_state.saved_temperature is not None:
            room_state.target_temperature = room_state.saved_temperature
        if room_state.saved_hvac_mode is not None:
            room_state.hvac_mode = room_state.saved_hvac_mode

        # Clear boost state
        room_state.preset_mode = PRESET_COMFORT
        room_state.boost_end_time = None
        room_state.saved_temperature = None
        room_state.saved_hvac_mode = None

        # Save state
        await self._save_state()

        # Notify listeners
        self.async_set_updated_data({})

        # Trigger processing to apply changes to physical ACs
        try:
            ac_names = list(self._room_states.keys())
            if ac_names:
                await self._process_group("multi_split", ac_names)
        except Exception as err:
            _LOGGER.error("Error processing ACs after temperature change: %s", err)

    def get_room_state(self, room_name: str) -> RoomState | None:
        """Get room state."""
        return self._room_states.get(room_name)

    async def _save_state(self):
        """Save state to storage."""
        data = {
            "rooms": {
                room_name: {
                    "target_temperature": state.target_temperature,
                    "hvac_mode": state.hvac_mode.value if state.hvac_mode else None,
                    "last_mode_switch": state.last_mode_switch.isoformat()
                    if state.last_mode_switch
                    else None,
                    "last_power_switch": state.last_power_switch.isoformat()
                    if state.last_power_switch
                    else None,
                }
                for room_name, state in self._room_states.items()
            }
        }
        await self._store.async_save(data)

    async def _restore_state(self):
        """Restore state from storage."""
        data = await self._store.async_load()
        if not data:
            return

        rooms_data = data.get("rooms", {})
        for room_name, room_data in rooms_data.items():
            if room_name not in self._room_states:
                continue

            room_state = self._room_states[room_name]

            if room_data.get("target_temperature") is not None:
                room_state.target_temperature = room_data["target_temperature"]

            if room_data.get("hvac_mode"):
                room_state.hvac_mode = HVACMode(room_data["hvac_mode"])

            if room_data.get("last_mode_switch"):
                room_state.last_mode_switch = dt_util.parse_datetime(
                    room_data["last_mode_switch"]
                )

            if room_data.get("last_power_switch"):
                room_state.last_power_switch = dt_util.parse_datetime(
                    room_data["last_power_switch"]
                )

            _LOGGER.info(
                "Restored state for room %s: mode=%s, temp=%s",
                room_name, room_state.hvac_mode, room_state.target_temperature
            )
