"""Value objects for domain layer."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class HVACMode(str, Enum):
    """HVAC modes - domain representation."""
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"
    DRY = "dry"
    FAN_ONLY = "fan_only"


class DecisionType(str, Enum):
    """Type of control decision."""
    NO_ACTION = "no_action"
    SET_MODE = "set_mode"
    SET_SETPOINT = "set_setpoint"
    SET_MODE_AND_SETPOINT = "set_mode_and_setpoint"
    TURN_OFF = "turn_off"


@dataclass(frozen=True)
class Temperature:
    """Temperature value object with validation."""
    value: float

    def __post_init__(self):
        if self.value < -50 or self.value > 100:
            raise ValueError(f"Temperature out of realistic range: {self.value}")

    def __float__(self) -> float:
        return self.value

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return Temperature(self.value + other)
        if isinstance(other, Temperature):
            return Temperature(self.value + other.value)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return Temperature(self.value - other)
        if isinstance(other, Temperature):
            return self.value - other.value
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (int, float)):
            return self.value < other
        if isinstance(other, Temperature):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, (int, float)):
            return self.value <= other
        if isinstance(other, Temperature):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, (int, float)):
            return self.value > other
        if isinstance(other, Temperature):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, (int, float)):
            return self.value >= other
        if isinstance(other, Temperature):
            return self.value >= other.value
        return NotImplemented


@dataclass(frozen=True)
class TemperatureRate:
    """Rate of temperature change (degrees per hour)."""
    degrees_per_hour: float


@dataclass(frozen=True)
class SensorSnapshot:
    """Snapshot of sensor readings at a point in time."""
    room_temperature: Temperature
    outdoor_temperature: Temperature
    timestamp: datetime
    temperature_rate: Optional[TemperatureRate] = None


@dataclass(frozen=True)
class DeviceCapabilities:
    """Capabilities of a climate device."""
    can_heat: bool
    can_cool: bool
    can_auto: bool
    can_dry: bool
    can_fan_only: bool
    min_setpoint: Temperature
    max_setpoint: Temperature
    supported_modes: frozenset[HVACMode]


@dataclass(frozen=True)
class DeviceState:
    """Current state of a climate device."""
    hvac_mode: HVACMode
    current_setpoint: Optional[Temperature]
    is_available: bool


@dataclass(frozen=True)
class ControlContext:
    """Context for making control decisions."""
    # Current state
    sensor_snapshot: SensorSnapshot
    device_state: DeviceState
    device_capabilities: DeviceCapabilities

    # Target and limits
    target_temperature: Temperature
    min_room_temp: Temperature
    max_room_temp: Temperature

    # Control parameters
    deadband: float
    base_offset: float
    dynamic_rate_factor: float
    max_dynamic_offset: float

    # Mode selection parameters
    outdoor_heat_threshold: float
    outdoor_cool_threshold: float
    mode_switch_hysteresis: float

    # Timing constraints
    last_mode_change: Optional[datetime]
    last_command_sent: Optional[datetime]
    min_mode_switch_interval: int  # seconds
    min_command_interval: int  # seconds

    # Current time
    now: datetime

    # Controller state
    controller_enabled: bool = True
    manual_mode_override: Optional[str] = None  # None = AUTO, "heat"/"cool" = manual mode


@dataclass(frozen=True)
class ControlDecision:
    """Decision made by the control engine."""
    decision_type: DecisionType
    desired_mode: Optional[HVACMode]
    desired_setpoint: Optional[Temperature]
    reason: str
    should_send_command: bool
    timestamp: datetime
