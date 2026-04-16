"""Domain models."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .value_objects import (
    Temperature,
    SensorSnapshot,
    DeviceCapabilities,
    DeviceState,
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
