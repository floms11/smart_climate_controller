"""Constants for Smart Climate Controller."""

DOMAIN = "smart_climate_controller"

# Config/Options keys
CONF_AC_UNITS = "ac_units"
CONF_AC_NAME = "ac_name"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_INDOOR_TEMP_SENSOR = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"

# Legacy keys for backward compatibility
CONF_ROOMS = "rooms"
CONF_ROOM_NAME = "room_name"
CONF_MULTI_SPLIT_GROUP = "multi_split_group"

# Global options
CONF_OUTDOOR_TEMP_HEAT_ONLY = "outdoor_temp_heat_only"
CONF_OUTDOOR_TEMP_COOL_ONLY = "outdoor_temp_cool_only"
CONF_MINOR_CORRECTION_HYSTERESIS = "minor_correction_hysteresis"
CONF_MINOR_CORRECTION_VALUE = "minor_correction_value"
CONF_MAJOR_CORRECTION_VALUE = "major_correction_value"
CONF_MAJOR_DEVIATION_THRESHOLD = "major_deviation_threshold"
CONF_MODE_SWITCH_TEMP_THRESHOLD = "mode_switch_temp_threshold"
CONF_USE_LINEAR_CORRECTION = "use_linear_correction"
CONF_MIN_MODE_SWITCH_INTERVAL = "min_mode_switch_interval"
CONF_MIN_POWER_SWITCH_INTERVAL = "min_power_switch_interval"
CONF_BOOST_TEMP_OFFSET = "boost_temp_offset"
CONF_BOOST_DURATION = "boost_duration"

# Defaults
DEFAULT_OUTDOOR_TEMP_HEAT_ONLY = 10.0
DEFAULT_OUTDOOR_TEMP_COOL_ONLY = 23.0
DEFAULT_MINOR_CORRECTION_HYSTERESIS = 0.5
DEFAULT_MINOR_CORRECTION_VALUE = 5.0
DEFAULT_MAJOR_CORRECTION_VALUE = 10.0
DEFAULT_MAJOR_DEVIATION_THRESHOLD = 1.0
DEFAULT_MODE_SWITCH_TEMP_THRESHOLD = 1.5
DEFAULT_USE_LINEAR_CORRECTION = False
DEFAULT_MIN_MODE_SWITCH_INTERVAL = 1800  # 30 minutes in seconds
DEFAULT_MIN_POWER_SWITCH_INTERVAL = 60  # 1 minute in seconds
DEFAULT_BOOST_TEMP_OFFSET = 5.0  # Temperature offset for boost modes
DEFAULT_BOOST_DURATION = 300  # 5 minutes in seconds

# Preset modes
PRESET_COMFORT = "comfort"
PRESET_BOOST_HEAT = "boost_heat"
PRESET_BOOST_COOL = "boost_cool"

# Storage
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1
