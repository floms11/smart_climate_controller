"""Temperature history tracker for dynamics calculation."""
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Optional
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class TemperatureTracker:
    """
    Tracks temperature history to calculate dynamics.

    Calculates:
    - Short-term dynamics (1 minute)
    - Long-term dynamics (10 minutes)
    """

    def __init__(self):
        """Initialize temperature tracker."""
        # Store tuples of (timestamp, temperature)
        self._history: deque[tuple[datetime, float]] = deque(maxlen=100)

    def add_measurement(self, temperature: float, timestamp: Optional[datetime] = None) -> None:
        """
        Add temperature measurement.

        Args:
            temperature: Temperature value in °C
            timestamp: Measurement timestamp (default: now)
        """
        if timestamp is None:
            timestamp = dt_util.utcnow()

        self._history.append((timestamp, temperature))

        # Clean old measurements (older than 15 minutes)
        cutoff = timestamp - timedelta(minutes=15)
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

        _LOGGER.debug(
            "Added temperature measurement: %.1f°C at %s, history size: %d",
            temperature,
            timestamp.isoformat(),
            len(self._history),
        )

    def get_short_term_rate(self, now: Optional[datetime] = None) -> Optional[float]:
        """
        Calculate short-term temperature change rate (°C per hour over last 1 minute).

        Returns:
            Rate in °C/hour, or None if insufficient data
        """
        return self._calculate_rate(minutes=1, now=now)

    def get_long_term_rate(self, now: Optional[datetime] = None) -> Optional[float]:
        """
        Calculate long-term temperature change rate (°C per hour over last 10 minutes).

        Returns:
            Rate in °C/hour, or None if insufficient data
        """
        return self._calculate_rate(minutes=10, now=now)

    def _calculate_rate(self, minutes: int, now: Optional[datetime] = None) -> Optional[float]:
        """
        Calculate temperature change rate over specified time period.

        Args:
            minutes: Time period in minutes
            now: Current timestamp (default: now)

        Returns:
            Rate in °C/hour, or None if insufficient data
        """
        if now is None:
            now = dt_util.utcnow()

        if len(self._history) < 2:
            _LOGGER.debug("Insufficient data for rate calculation: %d measurements", len(self._history))
            return None

        # Find measurements within time window
        cutoff = now - timedelta(minutes=minutes)

        # Get most recent measurement
        latest_time, latest_temp = self._history[-1]

        # Find oldest measurement within window
        oldest_temp = None
        oldest_time = None

        for timestamp, temp in self._history:
            if timestamp >= cutoff:
                oldest_temp = temp
                oldest_time = timestamp
                break

        if oldest_temp is None or oldest_time is None:
            _LOGGER.debug("No measurements found within %d minute window", minutes)
            return None

        # Calculate time delta in hours
        time_delta = (latest_time - oldest_time).total_seconds() / 3600.0

        # Require minimum time span - at least 50% of requested window
        min_time_delta = (minutes * 0.5) / 60.0  # Convert to hours
        if time_delta < min_time_delta:
            _LOGGER.debug(
                "Time span too short: %.1f min (need at least %.1f min for %d min window)",
                time_delta * 60,
                min_time_delta * 60,
                minutes
            )
            return None

        # Calculate rate (°C per hour)
        temp_delta = latest_temp - oldest_temp
        rate = temp_delta / time_delta

        # Sanity check: rate should be reasonable (not more than ±10°C/hour)
        if abs(rate) > 10.0:
            _LOGGER.warning(
                "Calculated rate %.2f°C/h seems unreasonable, returning None (%.2f°C over %.1f min)",
                rate,
                temp_delta,
                time_delta * 60,
            )
            return None

        # For stable temperature (no change), rate will be exactly 0
        # This is correct for wireless sensors that don't send updates when stable
        _LOGGER.debug(
            "Temperature rate (%d min window): %.2f°C/h (%.3f°C over %.1f min, %d measurements)",
            minutes,
            rate,
            temp_delta,
            time_delta * 60,
            len(self._history),
        )

        return rate

    def get_history_size(self) -> int:
        """Get number of measurements in history."""
        return len(self._history)

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()

    def to_dict(self) -> dict:
        """
        Serialize temperature history to dict for persistence.

        Returns:
            Dict with serialized history
        """
        return {
            "history": [
                {
                    "timestamp": timestamp.isoformat(),
                    "temperature": temp,
                }
                for timestamp, temp in self._history
            ]
        }

    def from_dict(self, data: dict) -> None:
        """
        Restore temperature history from dict.

        Args:
            data: Dict with serialized history
        """
        if not data or "history" not in data:
            _LOGGER.warning("No valid history data to restore")
            return

        self._history.clear()

        history_data = data["history"]
        if not isinstance(history_data, list):
            _LOGGER.error("Invalid history data format")
            return

        restored_count = 0
        for entry in history_data:
            try:
                timestamp_str = entry["timestamp"]
                temperature = entry["temperature"]

                # Parse ISO format timestamp
                timestamp = dt_util.parse_datetime(timestamp_str)
                if timestamp is None:
                    _LOGGER.warning("Failed to parse timestamp: %s", timestamp_str)
                    continue

                self._history.append((timestamp, temperature))
                restored_count += 1

            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Failed to restore history entry: %s", err)
                continue

        _LOGGER.info("Restored %d temperature measurements from persistent storage", restored_count)
