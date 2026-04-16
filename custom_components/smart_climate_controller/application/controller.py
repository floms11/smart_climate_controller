"""Main application controller - orchestrates control flow."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..domain.services.decision_engine import ClimateDecisionEngine
from ..domain.policies.mode_selection import OutdoorAwareModeSelectionPolicy
from ..domain.policies.setpoint_adjustment import DynamicSetpointAdjustmentPolicy
from ..domain.policies.safety import BasicSafetyPolicy
from ..domain.value_objects import (
    ControlDecision,
    DecisionType,
    TemperatureRate,
    SensorSnapshot,
    Temperature,
)
from .mapper import DomainMapper
from .commands import SetClimateCommand

_LOGGER = logging.getLogger(__name__)


class ClimateController:
    """
    Main application controller.

    Responsibilities:
    - Coordinate control cycle
    - Calculate temperature rate
    - Build control context
    - Invoke decision engine
    - Track state history
    """

    def __init__(self):
        """Initialize controller with policies."""
        # Initialize policies
        mode_policy = OutdoorAwareModeSelectionPolicy()
        setpoint_policy = DynamicSetpointAdjustmentPolicy()
        safety_policy = BasicSafetyPolicy()

        # Initialize decision engine
        self.decision_engine = ClimateDecisionEngine(
            mode_selection_policy=mode_policy,
            setpoint_policy=setpoint_policy,
            safety_policy=safety_policy,
        )

        # State tracking
        self.temperature_history: list[tuple[datetime, float]] = []
        self.last_mode_change: Optional[datetime] = None
        self.last_command_sent: Optional[datetime] = None
        self.last_decision: Optional[ControlDecision] = None

    def execute_control_cycle(
        self,
        # Sensor data
        room_temp: float,
        outdoor_temp: float,
        # Device state
        device_hvac_mode: str,
        device_setpoint: Optional[float],
        device_available: bool,
        device_supported_modes: list[str],
        device_min_temp: float,
        device_max_temp: float,
        # Configuration
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
        controller_enabled: bool,
        # Multi-split support
        multi_split_group_shared_mode: Optional[str] = None,
        # Optional overrides
        now: Optional[datetime] = None,
    ) -> tuple[Optional[SetClimateCommand], ControlDecision]:
        """
        Execute one control cycle.

        Returns:
            Tuple of (command_to_send, decision)
        """
        current_time = now or datetime.now()

        # Update temperature history
        self._update_temperature_history(room_temp, current_time)

        # Calculate temperature rate
        temp_rate = self._calculate_temperature_rate(current_time)

        # Create sensor snapshot
        sensor_snapshot = DomainMapper.create_sensor_snapshot(
            room_temp=room_temp,
            outdoor_temp=outdoor_temp,
            temp_rate=temp_rate,
            timestamp=current_time,
        )

        # Create device state and capabilities
        device_state = DomainMapper.create_device_state(
            hvac_mode=device_hvac_mode,
            current_temp=device_setpoint,
            is_available=device_available,
        )

        device_capabilities = DomainMapper.create_device_capabilities(
            supported_modes=device_supported_modes,
            min_temp=device_min_temp,
            max_temp=device_max_temp,
        )

        # Build control context
        context = DomainMapper.create_control_context(
            sensor_snapshot=sensor_snapshot,
            device_state=device_state,
            device_capabilities=device_capabilities,
            target_temp=target_temp,
            min_room_temp=min_room_temp,
            max_room_temp=max_room_temp,
            deadband=deadband,
            base_offset=base_offset,
            dynamic_rate_factor=dynamic_rate_factor,
            max_dynamic_offset=max_dynamic_offset,
            outdoor_heat_threshold=outdoor_heat_threshold,
            outdoor_cool_threshold=outdoor_cool_threshold,
            mode_switch_hysteresis=mode_switch_hysteresis,
            min_mode_switch_interval=min_mode_switch_interval,
            min_command_interval=min_command_interval,
            last_mode_change=self.last_mode_change,
            last_command_sent=self.last_command_sent,
            controller_enabled=controller_enabled,
            now=current_time,
        )

        # Make decision
        decision = self.decision_engine.make_decision(context)
        self.last_decision = decision

        # Build command if needed
        command = None
        if decision.should_send_command:
            command = self._build_command(decision, device_id="climate_device")

            # Update tracking
            self.last_command_sent = current_time
            if decision.desired_mode != device_state.hvac_mode:
                self.last_mode_change = current_time

        return command, decision

    def _update_temperature_history(self, temp: float, timestamp: datetime) -> None:
        """Update temperature history for rate calculation."""
        self.temperature_history.append((timestamp, temp))

        # Keep only last hour of data
        cutoff = timestamp - timedelta(hours=1)
        self.temperature_history = [
            (t, v) for t, v in self.temperature_history if t > cutoff
        ]

    def _calculate_temperature_rate(self, now: datetime) -> Optional[float]:
        """
        Calculate temperature change rate (degrees per hour).

        Uses linear regression over recent history for smooth rate estimation.
        """
        if len(self.temperature_history) < 3:
            return None

        # Use last 10 minutes of data for rate calculation
        recent_cutoff = now - timedelta(minutes=10)
        recent_data = [
            (t, v) for t, v in self.temperature_history if t > recent_cutoff
        ]

        if len(recent_data) < 2:
            return None

        # Simple rate: (last - first) / time_diff
        first_time, first_temp = recent_data[0]
        last_time, last_temp = recent_data[-1]

        time_diff_hours = (last_time - first_time).total_seconds() / 3600.0

        if time_diff_hours < 0.01:  # Less than ~36 seconds
            return None

        rate = (last_temp - first_temp) / time_diff_hours

        return rate

    def _build_command(
        self,
        decision: ControlDecision,
        device_id: str,
    ) -> SetClimateCommand:
        """Build command from decision."""
        return SetClimateCommand(
            device_id=device_id,
            hvac_mode=decision.desired_mode,
            target_temperature=decision.desired_setpoint,
        )

    def get_diagnostics(self) -> dict:
        """Get diagnostic information."""
        return {
            "temperature_history_size": len(self.temperature_history),
            "last_mode_change": self.last_mode_change.isoformat() if self.last_mode_change else None,
            "last_command_sent": self.last_command_sent.isoformat() if self.last_command_sent else None,
            "last_decision": {
                "type": self.last_decision.decision_type.value,
                "mode": self.last_decision.desired_mode.value if self.last_decision.desired_mode else None,
                "setpoint": self.last_decision.desired_setpoint.value if self.last_decision.desired_setpoint else None,
                "reason": self.last_decision.reason,
                "should_send": self.last_decision.should_send_command,
                "timestamp": self.last_decision.timestamp.isoformat(),
            } if self.last_decision else None,
        }
