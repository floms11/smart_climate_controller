"""Smart Climate Controller integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator
from .multi_split_coordinator import get_multi_split_coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate Controller from a config entry."""
    _LOGGER.info("Setting up Smart Climate Controller: %s", entry.data.get("zone_name"))

    # Migrate old entries to include missing default values
    from .const import (
        DEFAULT_DEADBAND, DEFAULT_MIN_ROOM_TEMP, DEFAULT_MAX_ROOM_TEMP,
        DEFAULT_MIN_AC_SETPOINT, DEFAULT_MAX_AC_SETPOINT,
        DEFAULT_OUTDOOR_HEAT_THRESHOLD, DEFAULT_OUTDOOR_COOL_THRESHOLD,
        DEFAULT_MODE_SWITCH_HYSTERESIS, DEFAULT_MIN_COMMAND_INTERVAL,
        DEFAULT_MIN_MODE_SWITCH_INTERVAL, DEFAULT_CONTROL_INTERVAL,
        DEFAULT_ENABLE_DEBUG_SENSORS,
        DEFAULT_MIN_RUN_TIME, DEFAULT_MIN_IDLE_TIME,
        DEFAULT_SETPOINT_ADJUSTMENT_INTERVAL, DEFAULT_SETPOINT_STEP,
    )

    updated_data = dict(entry.data)
    needs_update = False

    # Add missing defaults
    defaults = {
        "deadband": DEFAULT_DEADBAND,
        "min_room_temp": DEFAULT_MIN_ROOM_TEMP,
        "max_room_temp": DEFAULT_MAX_ROOM_TEMP,
        "min_ac_setpoint": DEFAULT_MIN_AC_SETPOINT,
        "max_ac_setpoint": DEFAULT_MAX_AC_SETPOINT,
        "outdoor_heat_threshold": DEFAULT_OUTDOOR_HEAT_THRESHOLD,
        "outdoor_cool_threshold": DEFAULT_OUTDOOR_COOL_THRESHOLD,
        "mode_switch_hysteresis": DEFAULT_MODE_SWITCH_HYSTERESIS,
        "min_command_interval": DEFAULT_MIN_COMMAND_INTERVAL,
        "min_mode_switch_interval": DEFAULT_MIN_MODE_SWITCH_INTERVAL,
        "control_interval": DEFAULT_CONTROL_INTERVAL,
        "enable_debug_sensors": DEFAULT_ENABLE_DEBUG_SENSORS,
        "min_run_time": DEFAULT_MIN_RUN_TIME,
        "min_idle_time": DEFAULT_MIN_IDLE_TIME,
        "setpoint_adjustment_interval": DEFAULT_SETPOINT_ADJUSTMENT_INTERVAL,
        "setpoint_step": DEFAULT_SETPOINT_STEP,
    }

    # Remove obsolete parameters from migrated configs
    obsolete_keys = ["base_offset", "dynamic_rate_factor", "max_dynamic_offset"]
    for key in obsolete_keys:
        if key in updated_data:
            del updated_data[key]
            needs_update = True
            _LOGGER.info("Removing obsolete config key '%s'", key)

    for key, default_value in defaults.items():
        if key not in updated_data:
            updated_data[key] = default_value
            needs_update = True
            _LOGGER.info("Adding missing config key '%s' with default value: %s", key, default_value)

    if needs_update:
        hass.config_entries.async_update_entry(entry, data=updated_data)

    # Create coordinator
    coordinator = SmartClimateCoordinator(
        hass=hass,
        entry_id=entry.entry_id,
        config=dict(updated_data),
    )

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register multi-split group if configured
    multi_split_group_id = entry.data.get("multi_split_group")
    if multi_split_group_id and multi_split_group_id.strip():
        multi_split_coordinator = get_multi_split_coordinator(hass)

        # Check if group already exists, if not create it
        if multi_split_group_id not in multi_split_coordinator.get_all_groups():
            zone_name = entry.data.get("zone_name", "Unknown Zone")
            multi_split_coordinator.register_group(
                group_id=multi_split_group_id,
                group_name=f"Multi-Split Group {multi_split_group_id}",
                zone_ids=[entry.entry_id],
            )
            _LOGGER.info("Created multi-split group: %s", multi_split_group_id)
        else:
            # Add this zone to existing group
            group = multi_split_coordinator.get_all_groups()[multi_split_group_id]
            if entry.entry_id not in group.zone_ids:
                group.add_zone(entry.entry_id)
                multi_split_coordinator.zone_to_group[entry.entry_id] = multi_split_group_id
                _LOGGER.info(
                    "Added zone %s to multi-split group %s",
                    entry.data.get("zone_name"),
                    multi_split_group_id,
                )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_set_target_temp(call):
        """Handle set target temperature service."""
        entry_id = call.data.get("entry_id")
        temperature = call.data.get("temperature")

        if entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return

        coordinator = hass.data[DOMAIN][entry_id]
        coordinator.set_target_temperature(temperature)
        await coordinator.async_request_refresh()

    async def handle_force_update(call):
        """Handle force update service."""
        entry_id = call.data.get("entry_id")

        if entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return

        coordinator = hass.data[DOMAIN][entry_id]
        await coordinator.async_force_update()

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, "set_target_temperature"):
        hass.services.async_register(
            DOMAIN,
            "set_target_temperature",
            handle_set_target_temp,
        )

    if not hass.services.has_service(DOMAIN, "force_update"):
        hass.services.async_register(
            DOMAIN,
            "force_update",
            handle_force_update,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Smart Climate Controller: %s", entry.data.get("zone_name"))

    # Save state before unloading
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info("Saving state before unload...")
        await coordinator.async_save_state()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
