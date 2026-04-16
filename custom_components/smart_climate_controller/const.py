"""Constants for Smart Climate Controller."""
from typing import Final

DOMAIN: Final = "smart_climate_controller"

# Config entry keys
CONF_ZONE_NAME: Final = "zone_name"
CONF_CLIMATE_ENTITY: Final = "climate_entity"
CONF_ROOM_TEMP_SENSOR: Final = "room_temp_sensor"
CONF_OUTDOOR_TEMP_SENSOR: Final = "outdoor_temp_sensor"
CONF_TARGET_TEMP: Final = "target_temp"
CONF_DEADBAND: Final = "deadband"
CONF_MIN_ROOM_TEMP: Final = "min_room_temp"
CONF_MAX_ROOM_TEMP: Final = "max_room_temp"
CONF_MIN_AC_SETPOINT: Final = "min_ac_setpoint"
CONF_MAX_AC_SETPOINT: Final = "max_ac_setpoint"
CONF_BASE_OFFSET: Final = "base_offset"
CONF_DYNAMIC_RATE_FACTOR: Final = "dynamic_rate_factor"
CONF_MAX_DYNAMIC_OFFSET: Final = "max_dynamic_offset"
CONF_OUTDOOR_HEAT_THRESHOLD: Final = "outdoor_heat_threshold"
CONF_OUTDOOR_COOL_THRESHOLD: Final = "outdoor_cool_threshold"
CONF_MODE_SWITCH_HYSTERESIS: Final = "mode_switch_hysteresis"
CONF_MIN_COMMAND_INTERVAL: Final = "min_command_interval"
CONF_MIN_MODE_SWITCH_INTERVAL: Final = "min_mode_switch_interval"
CONF_CONTROL_INTERVAL: Final = "control_interval"
CONF_ENABLE_DEBUG_SENSORS: Final = "enable_debug_sensors"
CONF_MULTI_SPLIT_GROUP: Final = "multi_split_group"

# Defaults
DEFAULT_ZONE_NAME: Final = "Climate Zone"
DEFAULT_TARGET_TEMP: Final = 21.0
DEFAULT_DEADBAND: Final = 0.5
DEFAULT_MIN_ROOM_TEMP: Final = 16.0
DEFAULT_MAX_ROOM_TEMP: Final = 30.0
DEFAULT_MIN_AC_SETPOINT: Final = 16.0
DEFAULT_MAX_AC_SETPOINT: Final = 30.0
DEFAULT_BASE_OFFSET: Final = 2.0
DEFAULT_DYNAMIC_RATE_FACTOR: Final = 10.0
DEFAULT_MAX_DYNAMIC_OFFSET: Final = 5.0
DEFAULT_OUTDOOR_HEAT_THRESHOLD: Final = 12.0
DEFAULT_OUTDOOR_COOL_THRESHOLD: Final = 18.0
DEFAULT_MODE_SWITCH_HYSTERESIS: Final = 1.0
DEFAULT_MIN_COMMAND_INTERVAL: Final = 30  # seconds
DEFAULT_MIN_MODE_SWITCH_INTERVAL: Final = 1800  # 30 minutes
DEFAULT_CONTROL_INTERVAL: Final = 60  # seconds
DEFAULT_ENABLE_DEBUG_SENSORS: Final = False

# Service names
SERVICE_SET_TARGET_TEMP: Final = "set_target_temperature"
SERVICE_FORCE_UPDATE: Final = "force_update"

# Attributes
ATTR_CONTROL_ACTIVE: Final = "control_active"
ATTR_LAST_DECISION: Final = "last_decision"
ATTR_LAST_DECISION_REASON: Final = "last_decision_reason"
ATTR_LAST_CONTROL_TIME: Final = "last_control_time"
ATTR_LAST_MODE_CHANGE: Final = "last_mode_change"
ATTR_ROOM_TEMP_RATE: Final = "room_temp_rate"
ATTR_OUTDOOR_TEMP: Final = "outdoor_temp"
ATTR_DESIRED_MODE: Final = "desired_mode"
ATTR_DESIRED_SETPOINT: Final = "desired_setpoint"
ATTR_MODE_LOCKED_UNTIL: Final = "mode_locked_until"
ATTR_COMMAND_LOCKED_UNTIL: Final = "command_locked_until"
ATTR_MULTI_SPLIT_GROUP: Final = "multi_split_group"
ATTR_GROUP_SHARED_MODE: Final = "group_shared_mode"
