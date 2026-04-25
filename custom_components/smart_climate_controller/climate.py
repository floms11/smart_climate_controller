"""Climate platform for Smart Climate Controller."""
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AC_NAME,
    CONF_AC_UNITS,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    DOMAIN,
    PRESET_BOOST_COOL,
    PRESET_BOOST_HEAT,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_ICONS,
)
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    # New format: CONF_AC_UNITS
    if CONF_AC_UNITS in entry.data:
        for ac_config in entry.data.get(CONF_AC_UNITS, []):
            ac_name = ac_config[CONF_AC_NAME]
            entities.append(SmartClimateThermostat(coordinator, ac_name))
    # Legacy format: CONF_ROOMS
    else:
        for room_config in entry.data.get(CONF_ROOMS, []):
            room_name = room_config[CONF_ROOM_NAME]
            entities.append(SmartClimateThermostat(coordinator, room_name))

    async_add_entities(entities)


class SmartClimateThermostat(CoordinatorEntity, ClimateEntity):
    """Thermostat for a room controlled by Smart Climate Controller."""

    _attr_has_entity_name = True
    _attr_translation_key = "smart_climate_controller"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    _attr_preset_modes = [
        PRESET_COMFORT,
        PRESET_BOOST_HEAT,
        PRESET_BOOST_COOL,
        PRESET_ECO,
    ]
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: SmartClimateCoordinator, room_name: str):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{room_name}"
        self._attr_name = room_name

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Smart Climate Controller",
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        room_state = self.coordinator.get_room_state(self._room_name)
        if room_state:
            return room_state.hvac_mode
        return HVACMode.OFF

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        room_state = self.coordinator.get_room_state(self._room_name)
        if room_state:
            return room_state.target_temperature
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from indoor sensor."""
        room_config = self.coordinator._get_room_config(self._room_name)
        if not room_config:
            return None

        from .const import CONF_INDOOR_TEMP_SENSOR
        indoor_sensor = room_config[CONF_INDOOR_TEMP_SENSOR]
        return self.coordinator._get_sensor_temperature(indoor_sensor)

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        room_state = self.coordinator.get_room_state(self._room_name)
        if room_state and hasattr(room_state, 'preset_mode'):
            return room_state.preset_mode
        return PRESET_COMFORT

    @property
    def icon(self) -> str:
        """Return the icon based on current preset mode."""
        return PRESET_ICONS.get(self.preset_mode, "mdi:home-thermometer-outline")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self.coordinator.set_room_hvac_mode(self._room_name, hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.coordinator.set_room_preset_mode(self._room_name, preset_mode)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.set_room_temperature(self._room_name, temperature)

        # If HVAC mode is provided, set it too
        if (hvac_mode := kwargs.get("hvac_mode")) is not None:
            await self.coordinator.set_room_hvac_mode(self._room_name, HVACMode(hvac_mode))

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        room_config = self.coordinator._get_room_config(self._room_name)
        if not room_config:
            return {}

        from .const import (
            CONF_CLIMATE_ENTITY,
            CONF_INDOOR_TEMP_SENSOR,
            CONF_MULTI_SPLIT_GROUP,
            CONF_OUTDOOR_TEMP_SENSOR,
        )

        attrs = {
            "climate_entity": room_config[CONF_CLIMATE_ENTITY],
            "indoor_temp_sensor": room_config[CONF_INDOOR_TEMP_SENSOR],
            "outdoor_temp_sensor": room_config[CONF_OUTDOOR_TEMP_SENSOR],
        }

        group_name = room_config.get(CONF_MULTI_SPLIT_GROUP, "").strip()
        if group_name:
            attrs["multi_split_group"] = group_name

        # Add outdoor temperature
        outdoor_temp = self.coordinator._get_sensor_temperature(
            room_config[CONF_OUTDOOR_TEMP_SENSOR]
        )
        if outdoor_temp is not None:
            attrs["outdoor_temperature"] = outdoor_temp

        # Add physical AC state
        climate_state = self.hass.states.get(room_config[CONF_CLIMATE_ENTITY])
        if climate_state:
            attrs["physical_hvac_mode"] = climate_state.state
            attrs["physical_temperature"] = climate_state.attributes.get("temperature")

        return attrs
