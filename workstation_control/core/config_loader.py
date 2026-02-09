"""
Config loader for workstation setup JSON files.

Config schema:
{
    "station_name": str,
    "plc": {
        "host": str,       # PLC IP address
        "port": int,       # Modbus TCP port (default 502)
        "unit_id": int     # Modbus unit/slave ID
    },
    "poll_interval_ms": int,  # Polling interval in ms (default 1000)
    "devices": [
        {
            "name": str,
            "type": "pump" | "motor" | "heater",
            "control_register": int,   # Coil/register address for on/off
            "status_register": int,    # Register address for reading status
            "setpoint_register": int,  # Register for speed/temperature setpoint (optional)
            "setpoint_unit": str,      # Unit label for setpoint (optional)
            "setpoint_min": float,     # Min setpoint value (optional)
            "setpoint_max": float      # Max setpoint value (optional)
        }
    ],
    "sensors": [
        {
            "tag": str,                # Tag name e.g. "TC-001"
            "name": str,               # Display name e.g. "Reactor Temperature"
            "category": "Temperature" | "Pressure" | "Flow",
            "register": int,           # Holding register address
            "data_type": "int16" | "uint16" | "int32" | "float32",
            "scale": float,            # Raw value * scale + offset = engineering value
            "offset": float,
            "unit": str,               # Engineering unit e.g. "°C", "bar", "L/min"
            "alarm_high": float,       # High alarm threshold (optional)
            "alarm_low": float         # Low alarm threshold (optional)
        }
    ]
}
"""

import json
import os


REQUIRED_PLC_KEYS = {"host", "port", "unit_id"}
REQUIRED_DEVICE_KEYS = {"name", "type", "control_register", "status_register"}
REQUIRED_SENSOR_KEYS = {"tag", "name", "category", "register", "unit"}
VALID_DEVICE_TYPES = {"pump", "motor", "heater"}
VALID_CATEGORIES = {"Temperature", "Pressure", "Flow"}
VALID_DATA_TYPES = {"int16", "uint16", "int32", "float32"}


class ConfigError(Exception):
    """Raised when config validation fails."""
    pass


def load_config(path: str) -> dict:
    """Load and validate a workstation config JSON file."""
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    _validate(config)
    _apply_defaults(config)
    return config


def _validate(cfg: dict):
    if "station_name" not in cfg:
        raise ConfigError("Missing 'station_name'")
    if "plc" not in cfg:
        raise ConfigError("Missing 'plc' section")

    missing = REQUIRED_PLC_KEYS - set(cfg["plc"].keys())
    if missing:
        raise ConfigError(f"PLC section missing keys: {missing}")

    if "devices" not in cfg or len(cfg["devices"]) == 0:
        raise ConfigError("At least one device is required")

    for i, dev in enumerate(cfg["devices"]):
        missing = REQUIRED_DEVICE_KEYS - set(dev.keys())
        if missing:
            raise ConfigError(f"Device [{i}] missing keys: {missing}")
        if dev["type"] not in VALID_DEVICE_TYPES:
            raise ConfigError(
                f"Device [{i}] invalid type '{dev['type']}', "
                f"must be one of {VALID_DEVICE_TYPES}"
            )

    if "sensors" not in cfg or len(cfg["sensors"]) == 0:
        raise ConfigError("At least one sensor is required")

    for i, sen in enumerate(cfg["sensors"]):
        missing = REQUIRED_SENSOR_KEYS - set(sen.keys())
        if missing:
            raise ConfigError(f"Sensor [{i}] missing keys: {missing}")
        if sen["category"] not in VALID_CATEGORIES:
            raise ConfigError(
                f"Sensor [{i}] invalid category '{sen['category']}', "
                f"must be one of {VALID_CATEGORIES}"
            )


def _apply_defaults(cfg: dict):
    cfg.setdefault("poll_interval_ms", 1000)
    cfg["plc"].setdefault("port", 502)
    cfg["plc"].setdefault("unit_id", 1)

    for dev in cfg["devices"]:
        dev.setdefault("setpoint_register", None)
        dev.setdefault("setpoint_unit", "")
        dev.setdefault("setpoint_min", 0)
        dev.setdefault("setpoint_max", 100)

    for sen in cfg["sensors"]:
        sen.setdefault("data_type", "uint16")
        sen.setdefault("scale", 1.0)
        sen.setdefault("offset", 0.0)
        sen.setdefault("alarm_high", None)
        sen.setdefault("alarm_low", None)
        if sen["data_type"] not in VALID_DATA_TYPES:
            sen["data_type"] = "uint16"
