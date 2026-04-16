"""Base adapter interface for climate devices."""
from abc import ABC, abstractmethod
from typing import Optional


class ClimateDeviceAdapter(ABC):
    """
    Abstract adapter for climate devices.

    Future implementations:
    - ClimateEntityAdapter (current MVP)
    - RecuperatorAdapter
    - MultiSplitAdapter
    - VentilationAdapter
    """

    @abstractmethod
    async def get_current_mode(self) -> str:
        """Get current HVAC mode."""
        pass

    @abstractmethod
    async def get_current_setpoint(self) -> Optional[float]:
        """Get current temperature setpoint."""
        pass

    @abstractmethod
    async def get_supported_modes(self) -> list[str]:
        """Get list of supported HVAC modes."""
        pass

    @abstractmethod
    async def get_temperature_limits(self) -> tuple[float, float]:
        """Get min and max temperature limits."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if device is available."""
        pass

    @abstractmethod
    async def set_mode(self, mode: str) -> bool:
        """Set HVAC mode."""
        pass

    @abstractmethod
    async def set_temperature(self, temperature: float) -> bool:
        """Set target temperature."""
        pass

    @abstractmethod
    async def set_mode_and_temperature(self, mode: str, temperature: float) -> bool:
        """Set both mode and temperature."""
        pass
