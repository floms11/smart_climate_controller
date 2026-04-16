"""Mappers between domain and HA representations."""
from typing import Optional
from datetime import datetime

from ..domain.value_objects import (
    Temperature,
    TemperatureRate,
    SensorSnapshot,
    DeviceCapabilities,
    DeviceState,
    ControlContext,
    HVACMode,
)


class DomainMapper:
    """Maps between HA state and domain objects."""

    @staticmethod
    def to_hvac_mode(ha_mode: str) -> HVACMode:
        """Convert HA HVAC mode string to domain enum."""
        mode_map = {
            "off": HVACMode.OFF,
            "heat": HVACMode.HEAT,
            "cool": HVACMode.COOL,
            "auto": HVACMode.AUTO,
            "dry": HVACMode.DRY,
            "fan_only": HVACMode.FAN_ONLY,
        }
        return mode_map.get(ha_mode, HVACMode.OFF)

    @staticmethod
    def from_hvac_mode(mode: HVACMode) -> str:
        """Convert domain HVAC mode to HA string."""
        return mode.value

    @staticmethod
    def create_sensor_snapshot(
        room_temp: float,
        outdoor_temp: float,
        temp_rate: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> SensorSnapshot:
        """Create sensor snapshot from raw values."""
        return SensorSnapshot(
            room_temperature=Temperature(room_temp),
            outdoor_temperature=Temperature(outdoor_temp),
            timestamp=timestamp or datetime.now(),
            temperature_rate=TemperatureRate(temp_rate) if temp_rate is not None else None,
        )

    @staticmethod
    def create_device_capabilities(
        supported_modes: list[str],
        min_temp: float,
        max_temp: float,
    ) -> DeviceCapabilities:
        """Create device capabilities from HA attributes."""
        modes = {DomainMapper.to_hvac_mode(m) for m in supported_modes}

        return DeviceCapabilities(
            can_heat=HVACMode.HEAT in modes,
            can_cool=HVACMode.COOL in modes,
            can_auto=HVACMode.AUTO in modes,
            can_dry=HVACMode.DRY in modes,
            can_fan_only=HVACMode.FAN_ONLY in modes,
            min_setpoint=Temperature(min_temp),
            max_setpoint=Temperature(max_temp),
            supported_modes=frozenset(modes),
        )

    @staticmethod
    def create_device_state(
        hvac_mode: str,
        current_temp: Optional[float],
        is_available: bool,
    ) -> DeviceState:
        """Create device state from HA state."""
        return DeviceState(
            hvac_mode=DomainMapper.to_hvac_mode(hvac_mode),
            current_setpoint=Temperature(current_temp) if current_temp is not None else None,
            is_available=is_available,
        )

    @staticmethod
    def create_control_context(
        sensor_snapshot: SensorSnapshot,
        device_state: DeviceState,
        device_capabilities: DeviceCapabilities,
        target_temp: float,
        min_room_temp: float,
        max_room_temp: float,
        deadband: float,
        base_offset: float,
        dynamic_rate_factor: float,
        max_dynamic_offset: float,
        outdoor_heat_threshold: float,
        outdoor_cool_threshold: float,
        mode_switch_hysteresis: float,
        min_mode_switch_interval: int,
        min_command_interval: int,
        last_mode_change: Optional[datetime],
        last_command_sent: Optional[datetime],
        controller_enabled: bool,
        now: Optional[datetime] = None,
    ) -> ControlContext:
        """Create control context from configuration and state."""
        return ControlContext(
            sensor_snapshot=sensor_snapshot,
            device_state=device_state,
            device_capabilities=device_capabilities,
            target_temperature=Temperature(target_temp),
            min_room_temp=Temperature(min_room_temp),
            max_room_temp=Temperature(max_room_temp),
            deadband=deadband,
            base_offset=base_offset,
            dynamic_rate_factor=dynamic_rate_factor,
            max_dynamic_offset=max_dynamic_offset,
            outdoor_heat_threshold=outdoor_heat_threshold,
            outdoor_cool_threshold=outdoor_cool_threshold,
            mode_switch_hysteresis=mode_switch_hysteresis,
            min_mode_switch_interval=min_mode_switch_interval,
            min_command_interval=min_command_interval,
            last_mode_change=last_mode_change,
            last_command_sent=last_command_sent,
            controller_enabled=controller_enabled,
            now=now or datetime.now(),
        )
