"""Home Assistant state reader."""
import logging
from typing import Optional

from homeassistant.core import HomeAssistant, State
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
)

_LOGGER = logging.getLogger(__name__)


class HAStateReader:
    """Reads state from Home Assistant entities."""

    def __init__(self, hass: HomeAssistant):
        """Initialize state reader."""
        self.hass = hass

    def get_temperature(self, entity_id: str) -> Optional[float]:
        """Get temperature from sensor entity."""
        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Entity %s not found", entity_id)
            return None

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.warning("Entity %s unavailable", entity_id)
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError) as err:
            _LOGGER.error("Cannot parse temperature from %s: %s", entity_id, err)
            return None

    def get_climate_state(self, entity_id: str) -> Optional[dict]:
        """Get climate entity state and attributes."""
        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Climate entity %s not found", entity_id)
            return None

        is_available = state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

        return {
            "hvac_mode": state.state if is_available else "off",
            "current_temperature": state.attributes.get("current_temperature"),
            "target_temperature": state.attributes.get(ATTR_TEMPERATURE),
            "min_temp": state.attributes.get(ATTR_MIN_TEMP, 16.0),
            "max_temp": state.attributes.get(ATTR_MAX_TEMP, 30.0),
            "hvac_modes": state.attributes.get(ATTR_HVAC_MODES, []),
            "is_available": is_available,
        }

    def is_entity_available(self, entity_id: str) -> bool:
        """Check if entity is available."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
