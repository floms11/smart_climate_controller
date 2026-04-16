"""Data coordinator for Smart Climate Controller."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .infrastructure.ha_state import HAStateReader
from .infrastructure.ha_commands import HACommandSender
from .infrastructure.temperature_tracker import TemperatureTracker
from .application.controller import ClimateController
from .application.commands import SetClimateCommand
from .multi_split_coordinator import get_multi_split_coordinator
from .domain.value_objects import DecisionType

_LOGGER = logging.getLogger(__name__)


class SmartClimateCoordinator(DataUpdateCoordinator):
    """Coordinator for smart climate control."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict,
    ):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=config.get("control_interval", 60)),
        )

        self.config = config
        self.entry_id = entry_id

        # Initialize infrastructure
        self.state_reader = HAStateReader(hass)
        self.command_sender = HACommandSender(hass)

        # Initialize application controller
        self.controller = ClimateController()

        # Temperature tracking for dynamics
        self.temp_tracker = TemperatureTracker()

        # Controller state
        self.controller_enabled = True
        self.manual_mode_override = None  # None = AUTO, or "heat"/"cool" for manual mode
        self._last_known_device_mode = None  # Track last known device mode

        # Anti-flapping state
        self.last_run_start: Optional[datetime] = None  # When AC turned on (OFF -> HEAT/COOL)
        self.last_idle_start: Optional[datetime] = None  # When AC turned off (HEAT/COOL -> OFF)
        self.last_setpoint_adjustment: Optional[datetime] = None  # Last time setpoint was adjusted

        # Multi-split support
        self.multi_split_coordinator = get_multi_split_coordinator(hass)
        self.multi_split_group_id = config.get("multi_split_group")

        # Setup state listener for climate entity
        self._setup_state_listener()

    async def _async_update_data(self):
        """Execute control cycle and return diagnostic data."""
        try:
            # Get entity IDs from config
            climate_entity = self.config["climate_entity"]
            room_sensor = self.config["room_temp_sensor"]
            outdoor_sensor = self.config["outdoor_temp_sensor"]

            # Read sensor data
            room_temp = self.state_reader.get_temperature(room_sensor)
            outdoor_temp = self.state_reader.get_temperature(outdoor_sensor)

            if room_temp is None or outdoor_temp is None:
                _LOGGER.warning(
                    "Sensor data unavailable: room_temp=%s, outdoor_temp=%s. Using safe data.",
                    room_temp,
                    outdoor_temp,
                )
                return self._get_safe_data()

            # Read device state
            climate_state = self.state_reader.get_climate_state(climate_entity)
            if climate_state is None:
                _LOGGER.warning("Climate entity unavailable")
                return self._get_safe_data()

            # Get current timestamp (timezone-aware)
            now = dt_util.utcnow()

            # Track temperature for dynamics calculation
            self.temp_tracker.add_measurement(room_temp, now)
            short_term_rate = self.temp_tracker.get_short_term_rate(now)
            long_term_rate = self.temp_tracker.get_long_term_rate(now)

            # Update last known device mode and anti-flapping timestamps
            device_mode = climate_state["hvac_mode"]

            # Update anti-flapping state on mode transitions
            if device_mode in ("heat", "cool") and self._last_known_device_mode == "off":
                # AC just turned on
                self.last_run_start = now
                self.last_idle_start = None
                _LOGGER.debug("AC turned on at %s", now.isoformat())
            elif device_mode == "off" and self._last_known_device_mode in ("heat", "cool"):
                # AC just turned off
                self.last_idle_start = now
                self.last_run_start = None
                _LOGGER.debug("AC turned off at %s", now.isoformat())

            self._last_known_device_mode = device_mode

            # Get multi-split shared mode if applicable
            multi_split_shared_mode = None
            if self.multi_split_group_id:
                multi_split_shared_mode = self.multi_split_coordinator.get_group_shared_mode(
                    self.entry_id
                )

            _LOGGER.debug(
                "Control cycle: manual=%s, enabled=%s, mode=%s, short_rate=%.2f°C/h, long_rate=%.2f°C/h",
                self.manual_mode_override,
                self.controller_enabled,
                device_mode,
                short_term_rate if short_term_rate is not None else 0.0,
                long_term_rate if long_term_rate is not None else 0.0,
            )

            # Execute control cycle
            command, decision = self.controller.execute_control_cycle(
                # Sensor data
                room_temp=room_temp,
                outdoor_temp=outdoor_temp,
                # Device state
                device_hvac_mode=climate_state["hvac_mode"],
                device_setpoint=climate_state["target_temperature"],
                device_available=climate_state["is_available"],
                device_supported_modes=climate_state["hvac_modes"],
                device_min_temp=climate_state["min_temp"],
                device_max_temp=climate_state["max_temp"],
                # Configuration
                target_temp=self.config["target_temp"],
                min_room_temp=self.config["min_room_temp"],
                max_room_temp=self.config["max_room_temp"],
                deadband=self.config["deadband"],
                outdoor_heat_threshold=self.config["outdoor_heat_threshold"],
                outdoor_cool_threshold=self.config["outdoor_cool_threshold"],
                mode_switch_hysteresis=self.config["mode_switch_hysteresis"],
                min_mode_switch_interval=self.config["min_mode_switch_interval"],
                min_command_interval=self.config["min_command_interval"],
                controller_enabled=self.controller_enabled,
                # New parameters
                short_term_rate=short_term_rate,
                long_term_rate=long_term_rate,
                last_run_start=self.last_run_start,
                last_idle_start=self.last_idle_start,
                min_run_time=self.config.get("min_run_time", 300),
                min_idle_time=self.config.get("min_idle_time", 180),
                last_setpoint_adjustment=self.last_setpoint_adjustment,
                setpoint_adjustment_interval=self.config.get("setpoint_adjustment_interval", 120),
                setpoint_step=self.config.get("setpoint_step", 1.0),
                # Multi-split support
                multi_split_group_shared_mode=multi_split_shared_mode.value if multi_split_shared_mode else None,
                # Manual mode override
                manual_mode_override=self.manual_mode_override,
            )

            # Update last_setpoint_adjustment if setpoint was changed
            if command is not None and decision.decision_type in (DecisionType.SET_SETPOINT, DecisionType.SET_MODE_AND_SETPOINT):
                self.last_setpoint_adjustment = now
                _LOGGER.debug("Setpoint adjusted at %s", now.isoformat())

            # Send command if needed
            if command is not None:
                _LOGGER.info(
                    "Sending command: mode=%s, temp=%s, should_send=%s",
                    command.hvac_mode.value,
                    command.target_temperature.value if command.target_temperature else "None",
                    decision.should_send_command,
                )
                await self.command_sender.send_climate_command(
                    command,
                    climate_entity,
                )
            else:
                _LOGGER.debug(
                    "No command to send. Decision: %s, should_send=%s, reason: %s",
                    decision.decision_type.value,
                    decision.should_send_command,
                    decision.reason,
                )

            # Get multi-split info if applicable
            multi_split_info = None
            if self.multi_split_group_id:
                group = self.multi_split_coordinator.get_group_for_zone(self.entry_id)
                if group:
                    multi_split_info = {
                        "group_id": group.group_id,
                        "group_name": group.group_name,
                        "shared_mode": group.current_shared_mode.value if group.current_shared_mode else None,
                        "last_mode_change": group.last_mode_change.isoformat() if group.last_mode_change else None,
                    }

            # Return diagnostic data
            return {
                "decision": decision,
                "command_sent": command is not None,
                "room_temp": room_temp,
                "outdoor_temp": outdoor_temp,
                "device_mode": climate_state["hvac_mode"],
                "device_setpoint": climate_state["target_temperature"],
                "short_term_rate": short_term_rate,
                "long_term_rate": long_term_rate,
                "controller_diagnostics": self.controller.get_diagnostics(),
                "multi_split_info": multi_split_info,
            }

        except Exception as err:
            _LOGGER.error("Error in control cycle: %s", err, exc_info=True)
            raise UpdateFailed(f"Control cycle failed: {err}") from err

    def _get_safe_data(self) -> dict:
        """Return safe/empty data when sensors unavailable."""
        # Try to at least get device state even if sensors are unavailable
        climate_entity = self.config.get("climate_entity")
        device_mode = None
        device_setpoint = None

        if climate_entity:
            try:
                climate_state = self.state_reader.get_climate_state(climate_entity)
                if climate_state:
                    device_mode = climate_state["hvac_mode"]
                    device_setpoint = climate_state["target_temperature"]
            except Exception as e:
                _LOGGER.debug("Could not read climate state in safe mode: %s", e)

        return {
            "decision": None,
            "command_sent": False,
            "room_temp": None,
            "outdoor_temp": None,
            "device_mode": device_mode,
            "device_setpoint": device_setpoint,
            "controller_diagnostics": None,
        }

    def set_target_temperature(self, temperature: float) -> None:
        """Set target temperature."""
        self.config["target_temp"] = temperature
        _LOGGER.info("Target temperature set to %.1f", temperature)

    def set_controller_enabled(self, enabled: bool) -> None:
        """Enable or disable controller."""
        self.controller_enabled = enabled
        _LOGGER.info("Controller %s", "enabled" if enabled else "disabled")

    def set_manual_mode(self, mode: Optional[str]) -> None:
        """Set manual mode override (None for AUTO, 'heat' or 'cool' for manual)."""
        self.manual_mode_override = mode
        if mode:
            _LOGGER.info("Manual mode override set to: %s", mode)
            # If in multi-split group, sync mode to all zones
            if self.multi_split_group_id:
                self._sync_group_mode(mode)
        else:
            _LOGGER.info("Manual mode override cleared (AUTO mode)")

    def _sync_group_mode(self, mode: str) -> None:
        """Sync manual mode to all zones in multi-split group."""
        if not self.multi_split_group_id:
            return

        group = self.multi_split_coordinator.get_group_for_zone(self.entry_id)
        if not group:
            return

        _LOGGER.info(
            "Syncing mode %s to all zones in group %s",
            mode,
            group.group_name,
        )

        # Set manual mode for all other zones in the group
        for zone_id in group.zone_ids:
            if zone_id == self.entry_id:
                continue  # Skip self

            # Get coordinator for this zone
            if zone_id in self.hass.data[DOMAIN]:
                other_coordinator = self.hass.data[DOMAIN][zone_id]
                other_coordinator.manual_mode_override = mode
                _LOGGER.debug("Set manual mode %s for zone %s", mode, zone_id)

                # Force immediate update for other zone to apply mode change
                self.hass.async_create_task(other_coordinator.async_request_refresh())

    async def async_force_update(self) -> None:
        """Force immediate control cycle."""
        await self.async_request_refresh()

    def _setup_state_listener(self) -> None:
        """Setup listener for climate entity state changes."""
        climate_entity = self.config.get("climate_entity")
        if not climate_entity:
            return

        async def state_change_listener(event):
            """Handle state changes of the climate entity."""
            # Filter: only handle events for our climate entity
            if event.data.get("entity_id") != climate_entity:
                return

            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")

            if new_state is None or old_state is None:
                return

            new_mode = new_state.state
            old_mode = old_state.state

            # Ignore if mode didn't change
            if new_mode == old_mode:
                return

            _LOGGER.info(
                "Climate entity mode changed: %s -> %s (manual_mode_override=%s, controller_enabled=%s)",
                old_mode,
                new_mode,
                self.manual_mode_override,
                self.controller_enabled,
            )

            # Get the desired mode from last decision (what integration wants)
            desired_mode = None
            if self.data and self.data.get("decision"):
                decision = self.data.get("decision")
                if decision.desired_mode:
                    desired_mode = decision.desired_mode.value

            # If user changed mode on AC and it doesn't match desired mode, restore it
            if desired_mode and new_mode != desired_mode and new_mode in ("heat", "cool", "off"):
                _LOGGER.warning(
                    "User manually changed AC mode to %s, but Desired HVAC Mode is %s. Restoring to %s.",
                    new_mode,
                    desired_mode,
                    desired_mode,
                )

                # Wait a bit to avoid race conditions
                await asyncio.sleep(0.5)

                # Restore the desired mode
                from .application.commands import SetClimateCommand
                from .domain.value_objects import HVACMode, Temperature

                if desired_mode in ("heat", "cool"):
                    # Get current target temperature from config
                    target_temp = self.config.get("target_temp", 24.0)
                    command = SetClimateCommand(
                        device_id=climate_entity,
                        hvac_mode=HVACMode(desired_mode),
                        target_temperature=Temperature(target_temp),
                    )
                    _LOGGER.info("Restoring AC mode to: %s with temp: %.1f", desired_mode, target_temp)
                    await self.command_sender.send_climate_command(command, climate_entity)
                elif desired_mode == "off":
                    command = SetClimateCommand(
                        device_id=climate_entity,
                        hvac_mode=HVACMode.OFF,
                        target_temperature=None,
                    )
                    _LOGGER.info("Restoring AC mode to: OFF")
                    await self.command_sender.send_climate_command(command, climate_entity)

            # Update last known device mode
            self._last_known_device_mode = new_mode

            # Trigger immediate update to refresh sensors
            self.hass.async_create_task(self.async_request_refresh())

        # Register listener without event filter (filtering is done inside callback)
        self.hass.bus.async_listen(
            "state_changed",
            state_change_listener,
        )
        _LOGGER.info("State listener registered for %s", climate_entity)
