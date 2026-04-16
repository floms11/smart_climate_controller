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
    CONF_CLIMATE_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_MAJOR_CORRECTION_VALUE,
    CONF_MAJOR_DEVIATION_THRESHOLD,
    CONF_MIN_MODE_SWITCH_INTERVAL,
    CONF_MIN_POWER_SWITCH_INTERVAL,
    CONF_MINOR_CORRECTION_HYSTERESIS,
    CONF_MINOR_CORRECTION_VALUE,
    CONF_MULTI_SPLIT_GROUP,
    CONF_OUTDOOR_TEMP_COOL_ONLY,
    CONF_OUTDOOR_TEMP_HEAT_ONLY,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    DEFAULT_MAJOR_CORRECTION_VALUE,
    DEFAULT_MAJOR_DEVIATION_THRESHOLD,
    DEFAULT_MIN_MODE_SWITCH_INTERVAL,
    DEFAULT_MIN_POWER_SWITCH_INTERVAL,
    DEFAULT_MINOR_CORRECTION_HYSTERESIS,
    DEFAULT_MINOR_CORRECTION_VALUE,
    DEFAULT_OUTDOOR_TEMP_COOL_ONLY,
    DEFAULT_OUTDOOR_TEMP_HEAT_ONLY,
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


class SmartClimateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Smart Climate Controller logic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Smart Climate Controller",
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._room_states: dict[str, RoomState] = {}
        self._climate_entities: dict[str, Any] = {}

        # Initialize room states
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
            # Process each multi-split group
            groups = self._get_multi_split_groups()
            for group_name, room_names in groups.items():
                await self._process_group(group_name, room_names)

            # Save state
            await self._save_state()

            return {}
        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}") from err

    async def async_shutdown(self):
        """Shutdown coordinator."""
        await self._save_state()

    def _get_multi_split_groups(self) -> dict[str, list[str]]:
        """Get multi-split groups from configuration."""
        groups: dict[str, list[str]] = {}

        for room_config in self.entry.data.get(CONF_ROOMS, []):
            room_name = room_config[CONF_ROOM_NAME]
            group_name = room_config.get(CONF_MULTI_SPLIT_GROUP, "").strip()

            if not group_name:
                # Independent room gets its own group
                group_name = f"_independent_{room_name}"

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(room_name)

        return groups

    def _get_room_config(self, room_name: str) -> dict[str, Any] | None:
        """Get room configuration."""
        for room_config in self.entry.data.get(CONF_ROOMS, []):
            if room_config[CONF_ROOM_NAME] == room_name:
                return room_config
        return None

    def _get_global_option(self, key: str, default: Any) -> Any:
        """Get global option value."""
        return self.entry.options.get(key, default)

    async def _process_group(self, group_name: str, room_names: list[str]):
        """Process a multi-split group."""
        _LOGGER.debug("Processing group %s with rooms: %s", group_name, room_names)

        # Step 1: Determine group's actual HVAC mode based on thermostat modes
        group_hvac_mode = self._determine_group_hvac_mode(room_names)
        _LOGGER.debug("Group %s hvac mode: %s", group_name, group_hvac_mode)

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
            _LOGGER.warning("Group %s: cannot determine physical mode", group_name)
            return

        _LOGGER.debug("Group %s: physical mode = %s", group_name, physical_mode)

        # Step 3: Control each room's climate based on physical mode
        for room_name in room_names:
            room_state = self._room_states.get(room_name)
            if not room_state or room_state.hvac_mode == HVACMode.OFF:
                _LOGGER.debug("Room %s: skipping (state=%s, mode=%s)",
                             room_name, room_state, room_state.hvac_mode if room_state else None)
                continue

            _LOGGER.debug("Room %s: controlling temperature (physical_mode=%s, target=%.1f)",
                         room_name, physical_mode, room_state.target_temperature)
            await self._control_room_temperature(room_name, physical_mode)

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

        # group_hvac_mode is AUTO - need to determine physical mode
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

        # Analyze room needs
        heat_need_score = 0
        cool_need_score = 0

        major_deviation_threshold = self._get_global_option(
            CONF_MAJOR_DEVIATION_THRESHOLD, DEFAULT_MAJOR_DEVIATION_THRESHOLD
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

            # Major deviation gets higher priority
            if temp_diff < -major_deviation_threshold:
                heat_need_score += 10  # Need heating badly
            elif temp_diff < 0:
                heat_need_score += 5  # Need heating

            if temp_diff > major_deviation_threshold:
                cool_need_score += 10  # Need cooling badly
            elif temp_diff > 0:
                cool_need_score += 5  # Need cooling

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

    async def _control_room_temperature(self, room_name: str, physical_mode: HVACMode):
        """Control room temperature based on physical mode.

        Implements minor and major temperature correction logic.
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

        ac_target_temp = None
        should_turn_off = False

        if physical_mode == HVACMode.HEAT:
            # Heating mode logic
            if temp_diff > major_threshold:
                # Room is too hot - turn off AC
                should_turn_off = True
            elif temp_diff < -major_threshold:
                # Room is too cold - major correction
                ac_target_temp = target_temp + major_correction
            elif temp_diff < -minor_hysteresis:
                # Room is slightly cold - minor correction
                ac_target_temp = target_temp + minor_correction
            else:
                # Within acceptable range - set target temp
                ac_target_temp = target_temp

        elif physical_mode == HVACMode.COOL:
            # Cooling mode logic
            if temp_diff < -major_threshold:
                # Room is too cold - turn off AC
                should_turn_off = True
            elif temp_diff > major_threshold:
                # Room is too hot - major correction
                ac_target_temp = target_temp - major_correction
            elif temp_diff > minor_hysteresis:
                # Room is slightly hot - minor correction
                ac_target_temp = target_temp - minor_correction
            else:
                # Within acceptable range - set target temp
                ac_target_temp = target_temp

        # Apply control
        if should_turn_off:
            await self._control_room_climate(room_name, HVACMode.OFF, None)
        else:
            await self._control_room_climate(room_name, physical_mode, ac_target_temp)

    async def _control_room_climate(
        self, room_name: str, hvac_mode: HVACMode, target_temperature: float | None
    ):
        """Control the physical climate entity for a room.

        Respects minimum power and mode switch intervals.
        """
        room_config = self._get_room_config(room_name)
        room_state = self._room_states.get(room_name)

        if not room_config or not room_state:
            return

        climate_entity_id = room_config[CONF_CLIMATE_ENTITY]
        climate_state = self.hass.states.get(climate_entity_id)

        if not climate_state:
            _LOGGER.warning("Climate entity %s not found", climate_entity_id)
            return

        current_mode = HVACMode(climate_state.state) if climate_state.state in HVACMode else None
        current_temp = climate_state.attributes.get("temperature")

        # Check if we need to change anything
        mode_changed = hvac_mode != current_mode
        temp_changed = (
            target_temperature is not None
            and (current_temp is None or abs(target_temperature - current_temp) > 0.1)
        )

        if not mode_changed and not temp_changed:
            _LOGGER.debug(
                "Room %s: no changes needed (mode: %s=%s, temp: %s=%s)",
                room_name, hvac_mode, current_mode, target_temperature, current_temp
            )
            return

        # Check minimum intervals
        now = dt_util.utcnow()

        if mode_changed:
            # Check mode switch interval
            min_mode_interval = self._get_global_option(
                CONF_MIN_MODE_SWITCH_INTERVAL, DEFAULT_MIN_MODE_SWITCH_INTERVAL
            )

            if room_state.last_mode_switch:
                time_since_switch = (now - room_state.last_mode_switch).total_seconds()
                if time_since_switch < min_mode_interval:
                    _LOGGER.debug(
                        "Room %s: skipping mode change (%.0f sec since last, min %d sec)",
                        room_name, time_since_switch, min_mode_interval
                    )
                    return

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
                    _LOGGER.debug(
                        "Room %s: skipping power change (%.0f sec since last, min %d sec)",
                        room_name, time_since_switch, min_power_interval
                    )
                    return

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

        # Synchronize group if needed
        room_config = self._get_room_config(room_name)
        if room_config:
            group_name = room_config.get(CONF_MULTI_SPLIT_GROUP, "").strip()
            if group_name:
                _LOGGER.debug("Synchronizing group %s after mode change in %s", group_name, room_name)
                await self._synchronize_group_modes(group_name, room_name, hvac_mode)

        # Save state immediately
        await self._save_state()

        # Notify all listeners that data has changed (updates UI)
        self.async_set_updated_data({})

        # Trigger processing to apply changes to physical ACs
        try:
            groups = self._get_multi_split_groups()
            for group_name, room_names in groups.items():
                await self._process_group(group_name, room_names)
        except Exception as err:
            _LOGGER.error("Error processing groups after mode change: %s", err)

    async def _synchronize_group_modes(
        self, group_name: str, initiating_room: str, new_mode: HVACMode
    ):
        """Synchronize thermostat modes within a multi-split group.

        When one thermostat changes to heat/cool/auto, all other active
        thermostats in the group should switch to the same mode.
        """
        if new_mode == HVACMode.OFF:
            # OFF mode doesn't trigger synchronization
            _LOGGER.debug("Skipping synchronization for OFF mode in group %s", group_name)
            return

        # Find all rooms in this group
        group_rooms = []
        for room_config in self.entry.data.get(CONF_ROOMS, []):
            if room_config.get(CONF_MULTI_SPLIT_GROUP, "").strip() == group_name:
                group_rooms.append(room_config[CONF_ROOM_NAME])

        _LOGGER.debug("Group %s rooms: %s, initiating room: %s", group_name, group_rooms, initiating_room)

        # Update other rooms in the group
        synchronized_count = 0
        for room_name in group_rooms:
            if room_name == initiating_room:
                continue

            room_state = self._room_states.get(room_name)
            if not room_state:
                _LOGGER.warning("Room state not found for %s during synchronization", room_name)
                continue

            # Only synchronize if room is not OFF
            if room_state.hvac_mode != HVACMode.OFF:
                old_mode = room_state.hvac_mode
                room_state.hvac_mode = new_mode
                room_state.last_mode_switch = dt_util.utcnow()
                synchronized_count += 1
                _LOGGER.info(
                    "Synchronized room %s: %s -> %s (group %s)",
                    room_name, old_mode, new_mode, group_name
                )
            else:
                _LOGGER.debug("Skipping room %s: already OFF", room_name)

        _LOGGER.info("Synchronized %d rooms in group %s to mode %s", synchronized_count, group_name, new_mode)

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

        # Trigger processing to apply changes to physical ACs
        try:
            groups = self._get_multi_split_groups()
            for group_name, room_names in groups.items():
                await self._process_group(group_name, room_names)
        except Exception as err:
            _LOGGER.error("Error processing groups after temperature change: %s", err)

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
