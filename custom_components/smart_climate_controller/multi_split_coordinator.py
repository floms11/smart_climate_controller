"""Multi-split group coordinator for Home Assistant."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import HVACMode

from .const import DOMAIN
from .domain.models import MultiSplitGroup
from .domain.services.multi_split_coordinator import MultiSplitModeSelector

_LOGGER = logging.getLogger(__name__)


class MultiSplitGroupCoordinator:
    """
    Coordinates multi-split HVAC groups in Home Assistant.

    Manages multiple climate zones that share a common outdoor unit,
    ensuring all zones operate in the same heating/cooling mode.
    """

    def __init__(self, hass: HomeAssistant):
        """Initialize multi-split coordinator."""
        self.hass = hass
        self.groups: dict[str, MultiSplitGroup] = {}
        self.mode_selector = MultiSplitModeSelector()

        # Track zone-to-group mapping
        self.zone_to_group: dict[str, str] = {}

    def register_group(
        self,
        group_id: str,
        group_name: str,
        zone_ids: list[str],
    ) -> None:
        """
        Register a new multi-split group.

        Args:
            group_id: Unique identifier for the group
            group_name: Human-readable name
            zone_ids: List of zone/entry IDs belonging to this group
        """
        if group_id in self.groups:
            _LOGGER.warning("Multi-split group %s already registered", group_id)
            return

        group = MultiSplitGroup(
            group_id=group_id,
            group_name=group_name,
            zone_ids=zone_ids,
        )

        self.groups[group_id] = group

        # Update zone-to-group mapping
        for zone_id in zone_ids:
            self.zone_to_group[zone_id] = group_id

        _LOGGER.info(
            "Registered multi-split group '%s' with %d zones: %s",
            group_name,
            len(zone_ids),
            zone_ids,
        )

    def get_group_for_zone(self, zone_id: str) -> Optional[MultiSplitGroup]:
        """Get the multi-split group for a given zone."""
        group_id = self.zone_to_group.get(zone_id)
        if group_id:
            return self.groups.get(group_id)
        return None

    def get_group_shared_mode(self, zone_id: str) -> Optional[HVACMode]:
        """Get the shared mode for the group this zone belongs to."""
        group = self.get_group_for_zone(zone_id)
        if group:
            return group.current_shared_mode
        return None

    def update_group_mode(
        self,
        group_id: str,
        mode: HVACMode,
        now: Optional[datetime] = None,
    ) -> None:
        """
        Update the shared mode for a multi-split group.

        Args:
            group_id: Group identifier
            mode: New HVAC mode
            now: Current timestamp (for testing)
        """
        if group_id not in self.groups:
            _LOGGER.error("Multi-split group %s not found", group_id)
            return

        timestamp = now or datetime.now()
        group = self.groups[group_id]
        old_mode = group.current_shared_mode

        group.update_shared_mode(mode, timestamp)

        _LOGGER.info(
            "Multi-split group '%s' mode changed: %s -> %s",
            group.group_name,
            old_mode,
            mode,
        )

    def is_zone_in_multi_split(self, zone_id: str) -> bool:
        """Check if a zone is part of a multi-split group."""
        return zone_id in self.zone_to_group

    def get_all_groups(self) -> dict[str, MultiSplitGroup]:
        """Get all registered multi-split groups."""
        return self.groups

    def get_group_diagnostics(self, group_id: str) -> Optional[dict]:
        """Get diagnostic information for a multi-split group."""
        if group_id not in self.groups:
            return None

        group = self.groups[group_id]
        return {
            "group_id": group.group_id,
            "group_name": group.group_name,
            "zone_ids": group.zone_ids,
            "current_shared_mode": group.current_shared_mode.value if group.current_shared_mode else None,
            "last_mode_change": group.last_mode_change.isoformat() if group.last_mode_change else None,
            "zone_count": len(group.zone_ids),
        }


def get_multi_split_coordinator(hass: HomeAssistant) -> MultiSplitGroupCoordinator:
    """Get or create the multi-split coordinator for this Home Assistant instance."""
    if f"{DOMAIN}_multi_split" not in hass.data:
        hass.data[f"{DOMAIN}_multi_split"] = MultiSplitGroupCoordinator(hass)
    return hass.data[f"{DOMAIN}_multi_split"]
