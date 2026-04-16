"""Command objects for device control."""
from dataclasses import dataclass
from typing import Optional

from ..domain.value_objects import HVACMode, Temperature


@dataclass(frozen=True)
class SetClimateCommand:
    """Command to set climate device state."""
    device_id: str
    hvac_mode: HVACMode
    target_temperature: Optional[Temperature] = None


@dataclass(frozen=True)
class SetTemperatureCommand:
    """Command to set only temperature (preserve mode)."""
    device_id: str
    target_temperature: Temperature


@dataclass(frozen=True)
class SetModeCommand:
    """Command to set only HVAC mode."""
    device_id: str
    hvac_mode: HVACMode
