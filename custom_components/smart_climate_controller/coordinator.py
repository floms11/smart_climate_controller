"""Data coordinator for Smart Climate Controller."""
import logging
from datetime import timedelta
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .infrastructure.ha_state import HAStateReader
from .infrastructure.ha_commands import HACommandSender
from .application.controller import ClimateController
from .application.commands import SetClimateCommand
from .multi_split_coordinator import get_multi_split_coordinator

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

        # Controller state
        self.controller_enabled = True
        self.manual_mode_override = None  # None = AUTO, or "heat"/"cool" for manual mode
        self._last_known_device_mode = None  # Track last known device mode

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
                _LOGGER.warning("Sensor data unavailable")
                return self._get_safe_data()

            # Read device state
            climate_state = self.state_reader.get_climate_state(climate_entity)
            if climate_state is None:
                _LOGGER.warning("Climate entity unavailable")
                return self._get_safe_data()

            # Update last known device mode
            device_mode = climate_state["hvac_mode"]
            self._last_known_device_mode = device_mode

            # Get multi-split shared mode if applicable
            multi_split_shared_mode = None
            if self.multi_split_group_id:
                multi_split_shared_mode = self.multi_split_coordinator.get_group_shared_mode(
                    self.entry_id
                )

            _LOGGER.debug(
                "Control cycle starting: manual_mode=%s, controller_enabled=%s, device_mode=%s",
                self.manual_mode_override,
                self.controller_enabled,
                climate_state["hvac_mode"],
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
                base_offset=self.config["base_offset"],
                dynamic_rate_factor=self.config["dynamic_rate_factor"],
                max_dynamic_offset=self.config["max_dynamic_offset"],
                outdoor_heat_threshold=self.config["outdoor_heat_threshold"],
                outdoor_cool_threshold=self.config["outdoor_cool_threshold"],
                mode_switch_hysteresis=self.config["mode_switch_hysteresis"],
                min_mode_switch_interval=self.config["min_mode_switch_interval"],
                min_command_interval=self.config["min_command_interval"],
                controller_enabled=self.controller_enabled,
                # Multi-split support
                multi_split_group_shared_mode=multi_split_shared_mode.value if multi_split_shared_mode else None,
                # Manual mode override
                manual_mode_override=self.manual_mode_override,
            )

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
                "controller_diagnostics": self.controller.get_diagnostics(),
                "multi_split_info": multi_split_info,
            }

        except Exception as err:
            _LOGGER.error("Error in control cycle: %s", err, exc_info=True)
            raise UpdateFailed(f"Control cycle failed: {err}") from err

    def _get_safe_data(self) -> dict:
        """Return safe/empty data when sensors unavailable."""
        return {
            "decision": None,
            "command_sent": False,
            "room_temp": None,
            "outdoor_temp": None,
            "device_mode": None,
            "device_setpoint": None,
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

            # Determine what mode the integration expects
            expected_mode = None
            if not self.controller_enabled:
                expected_mode = "off"
            elif self.manual_mode_override:
                expected_mode = self.manual_mode_override
            # For AUTO mode (no manual override), we don't have a fixed expected_mode

            # If user changed mode on AC (not through integration), restore expected mode
            if expected_mode and new_mode != expected_mode:
                _LOGGER.warning(
                    "User manually changed AC mode to %s, but integration expects %s. Restoring integration mode.",
                    new_mode,
                    expected_mode,
                )

                # Wait a bit to avoid race conditions
                await asyncio.sleep(0.5)

                # Restore the expected mode
                from .application.commands import SetClimateCommand
                from .domain.value_objects import HVACMode, Temperature

                if expected_mode in ("heat", "cool"):
                    # Get current target temperature from config
                    target_temp = self.config.get("target_temp", 24.0)
                    command = SetClimateCommand(
                        device_id=climate_entity,
                        hvac_mode=HVACMode(expected_mode),
                        target_temperature=Temperature(target_temp),
                    )
                    _LOGGER.info("Restoring mode to: %s with temp: %.1f", expected_mode, target_temp)
                    await self.command_sender.send_climate_command(command, climate_entity)
                elif expected_mode == "off":
                    command = SetClimateCommand(
                        device_id=climate_entity,
                        hvac_mode=HVACMode.OFF,
                        target_temperature=None,
                    )
                    _LOGGER.info("Restoring mode to: OFF")
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
