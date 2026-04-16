"""Base policy interfaces."""
from abc import ABC, abstractmethod
from typing import Optional

from ..value_objects import HVACMode, ControlContext, Temperature


class ModeSelectionPolicy(ABC):
    """Policy for selecting HVAC mode based on conditions."""

    @abstractmethod
    def select_mode(
        self,
        current_mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        outdoor_temp: Temperature,
        context: ControlContext,
    ) -> tuple[HVACMode, str]:
        """
        Select appropriate HVAC mode.

        Returns:
            Tuple of (desired_mode, reason)
        """
        pass


class SetpointAdjustmentPolicy(ABC):
    """Policy for calculating device setpoint."""

    @abstractmethod
    def calculate_setpoint(
        self,
        mode: HVACMode,
        room_temp: Temperature,
        target_temp: Temperature,
        temp_rate: Optional[float],
        context: ControlContext,
    ) -> tuple[Temperature, str]:
        """
        Calculate desired setpoint for the device.

        Returns:
            Tuple of (setpoint, reason)
        """
        pass


class SafetyPolicy(ABC):
    """Policy for safety checks and emergency stops."""

    @abstractmethod
    def should_emergency_stop(
        self,
        context: ControlContext,
    ) -> tuple[bool, str]:
        """
        Check if device should be stopped for safety.

        Returns:
            Tuple of (should_stop, reason)
        """
        pass
