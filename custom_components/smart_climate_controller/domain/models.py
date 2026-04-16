"""Domain models."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

from .value_objects import (
    Temperature,
    SensorSnapshot,
    DeviceCapabilities,
    DeviceState,
    HVACMode,
)


@dataclass
class ClimateDevice:
    """Represents a controllable climate device."""
    device_id: str
    device_type: str  # "air_conditioner", "recuperator", "heater", etc.
    capabilities: DeviceCapabilities
    current_state: DeviceState
    last_command_time: Optional[datetime] = None

    def update_state(self, new_state: DeviceState) -> None:
        """Update device state."""
        self.current_state = new_state


@dataclass
class ClimateZone:
    """Represents a climate zone (room or group of rooms)."""
    zone_id: str
    zone_name: str
    target_temperature: Temperature
    devices: list[ClimateDevice] = field(default_factory=list)
    sensor_snapshots: list[SensorSnapshot] = field(default_factory=list)
    multi_split_group_id: Optional[str] = None

    def add_device(self, device: ClimateDevice) -> None:
        """Add a device to this zone."""
        self.devices.append(device)

    def update_sensors(self, snapshot: SensorSnapshot) -> None:
        """Update sensor readings."""
        self.sensor_snapshots.append(snapshot)
        # Keep only last 100 snapshots for rate calculation
        if len(self.sensor_snapshots) > 100:
            self.sensor_snapshots = self.sensor_snapshots[-100:]

    def get_primary_device(self) -> Optional[ClimateDevice]:
        """Get primary climate device (for MVP - the only device)."""
        return self.devices[0] if self.devices else None


@dataclass
class MultiSplitGroup:
    """
    Represents a multi-split system group.

    All zones in the group must operate in the same HVAC mode (HEAT or COOL).
    Individual units can be turned OFF, but mode changes affect the entire group.
    """
    group_id: str
    group_name: str
    zone_ids: list[str] = field(default_factory=list)
    current_shared_mode: Optional[HVACMode] = None
    last_mode_change: Optional[datetime] = None

    def add_zone(self, zone_id: str) -> None:
        """Add a zone to this multi-split group."""
        if zone_id not in self.zone_ids:
            self.zone_ids.append(zone_id)

    def remove_zone(self, zone_id: str) -> None:
        """Remove a zone from this multi-split group."""
        if zone_id in self.zone_ids:
            self.zone_ids.remove(zone_id)

    def update_shared_mode(self, mode: HVACMode, timestamp: datetime) -> None:
        """Update the shared mode for all zones in the group."""
        self.current_shared_mode = mode
        self.last_mode_change = timestamp

    def can_change_mode(self, min_mode_switch_interval: int, now: datetime) -> bool:
        """Check if mode can be changed based on minimum interval."""
        if self.last_mode_change is None:
            return True
        elapsed = (now - self.last_mode_change).total_seconds()
        return elapsed >= min_mode_switch_interval
