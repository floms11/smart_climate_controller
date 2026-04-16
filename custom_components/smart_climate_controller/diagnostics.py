"""Diagnostics support for Smart Climate Controller."""
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    diagnostics = {
        "config": dict(entry.data),
        "controller_enabled": coordinator.controller_enabled,
        "last_update_success": coordinator.last_update_success,
        "last_update_time": coordinator.last_update_success_time.isoformat() if coordinator.last_update_success_time else None,
    }

    if coordinator.data:
        diagnostics["current_state"] = {
            "room_temp": coordinator.data.get("room_temp"),
            "outdoor_temp": coordinator.data.get("outdoor_temp"),
            "device_mode": coordinator.data.get("device_mode"),
            "device_setpoint": coordinator.data.get("device_setpoint"),
            "command_sent": coordinator.data.get("command_sent"),
        }

        if coordinator.data.get("decision"):
            decision = coordinator.data["decision"]
            diagnostics["last_decision"] = {
                "type": decision.decision_type.value,
                "mode": decision.desired_mode.value if decision.desired_mode else None,
                "setpoint": decision.desired_setpoint.value if decision.desired_setpoint else None,
                "reason": decision.reason,
                "should_send": decision.should_send_command,
                "timestamp": decision.timestamp.isoformat(),
            }

        if coordinator.data.get("controller_diagnostics"):
            diagnostics["controller"] = coordinator.data["controller_diagnostics"]

    return diagnostics
