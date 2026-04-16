"""Smart Climate Controller integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate Controller from a config entry."""
    _LOGGER.info("Setting up Smart Climate Controller: %s", entry.data.get("zone_name"))

    # Create coordinator
    coordinator = SmartClimateCoordinator(
        hass=hass,
        entry_id=entry.entry_id,
        config=dict(entry.data),
    )

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
