"""
Modbus TCP client for PLC communication.

Handles:
- Connection management to PLC via Modbus TCP
- Periodic polling of sensor registers (1-second interval)
- Writing control commands (coils and holding registers)
- Data type conversion (int16, uint16, int32, float32)
"""

import struct
import time
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


class SensorReading:
    """A single sensor data point."""
    __slots__ = ("tag", "name", "category", "value", "unit", "timestamp", "alarm")

    def __init__(self, tag, name, category, value, unit, timestamp, alarm=None):
        self.tag = tag
        self.name = name
        self.category = category
        self.value = value
        self.unit = unit
        self.timestamp = timestamp
        self.alarm = alarm  # None, "HIGH", or "LOW"


class ModbusClient(QObject):
    """
    Modbus TCP client that polls PLC sensor data and sends control commands.

    Signals:
        data_received(list[SensorReading]): Emitted every poll cycle with all sensor readings.
        connection_changed(bool): Emitted when connection state changes.
        error_occurred(str): Emitted on communication errors.
    """

    data_received = pyqtSignal(list)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        plc = config["plc"]
        self._host = plc["host"]
        self._port = plc["port"]
        self._unit_id = plc["unit_id"]
        self._sensors = config["sensors"]
        self._devices = config["devices"]
        self._poll_interval = config.get("poll_interval_ms", 1000)

        self._client = ModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=3,
            retries=2,
        )
        self._connected = False
        self._consecutive_errors = 0
        self._max_errors_before_reconnect = 5

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Establish connection to the PLC."""
        try:
            result = self._client.connect()
            if result:
                self._connected = True
                self._consecutive_errors = 0
                self.connection_changed.emit(True)
                return True
            else:
                self._connected = False
                self.connection_changed.emit(False)
                self.error_occurred.emit(
                    f"Failed to connect to {self._host}:{self._port}"
                )
                return False
        except Exception as e:
            self._connected = False
            self.connection_changed.emit(False)
            self.error_occurred.emit(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the PLC and stop polling."""
        self.stop_polling()
        self._client.close()
        self._connected = False
        self.connection_changed.emit(False)

    def start_polling(self):
        """Start periodic sensor polling."""
        if not self._connected:
            self.error_occurred.emit("Cannot start polling: not connected")
            return
        self._poll_timer.start(self._poll_interval)

    def stop_polling(self):
        """Stop periodic sensor polling."""
        self._poll_timer.stop()

    def _poll(self):
        """Read all sensor registers and emit data."""
        readings = []
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")

        for sensor in self._sensors:
            try:
                value = self._read_sensor(sensor)
                alarm = self._check_alarm(sensor, value)
                reading = SensorReading(
                    tag=sensor["tag"],
                    name=sensor["name"],
                    category=sensor["category"],
                    value=value,
                    unit=sensor["unit"],
                    timestamp=timestamp,
                    alarm=alarm,
                )
                readings.append(reading)
                self._consecutive_errors = 0
            except (ModbusException, Exception) as e:
                self._consecutive_errors += 1
                self.error_occurred.emit(
                    f"Read error [{sensor['tag']}]: {e}"
                )
                if self._consecutive_errors >= self._max_errors_before_reconnect:
                    self._handle_reconnect()
                    return

        if readings:
            self.data_received.emit(readings)

    def _read_sensor(self, sensor: dict) -> float:
        """Read a single sensor value from PLC registers."""
        addr = sensor["register"]
        dtype = sensor.get("data_type", "uint16")
        scale = sensor.get("scale", 1.0)
        offset = sensor.get("offset", 0.0)

        if dtype in ("int32", "float32"):
            count = 2
        else:
            count = 1

        result = self._client.read_holding_registers(
            address=addr, count=count, slave=self._unit_id
        )
        if result.isError():
            raise ModbusException(f"Modbus error at register {addr}: {result}")

        raw = self._decode_registers(result.registers, dtype)
        return raw * scale + offset

    def _decode_registers(self, registers: list, dtype: str):
        """Decode raw register values to the specified data type."""
        if dtype == "uint16":
            return registers[0]
        elif dtype == "int16":
            val = registers[0]
            return val - 65536 if val >= 32768 else val
        elif dtype == "int32":
            raw_bytes = struct.pack(">HH", registers[0], registers[1])
            return struct.unpack(">i", raw_bytes)[0]
        elif dtype == "float32":
            raw_bytes = struct.pack(">HH", registers[0], registers[1])
            return struct.unpack(">f", raw_bytes)[0]
        return registers[0]

    def _check_alarm(self, sensor: dict, value: float):
        """Check if value exceeds alarm thresholds."""
        high = sensor.get("alarm_high")
        low = sensor.get("alarm_low")
        if high is not None and value >= high:
            return "HIGH"
        if low is not None and value <= low:
            return "LOW"
        return None

    def _handle_reconnect(self):
        """Attempt to reconnect after consecutive errors."""
        self.stop_polling()
        self._connected = False
        self.connection_changed.emit(False)
        self.error_occurred.emit(
            "Too many consecutive errors. Attempting reconnect..."
        )
        self._client.close()
        time.sleep(1)
        if self.connect():
            self.start_polling()

    # ── Device Control Methods ──────────────────────────────────────────

    def write_coil(self, address: int, value: bool) -> bool:
        """Write a single coil (on/off control)."""
        try:
            result = self._client.write_coil(
                address=address, value=value, slave=self._unit_id
            )
            if result.isError():
                self.error_occurred.emit(f"Write coil error at {address}: {result}")
                return False
            return True
        except Exception as e:
            self.error_occurred.emit(f"Write coil exception: {e}")
            return False

    def write_register(self, address: int, value: int) -> bool:
        """Write a single holding register (setpoint)."""
        try:
            result = self._client.write_register(
                address=address, value=value, slave=self._unit_id
            )
            if result.isError():
                self.error_occurred.emit(f"Write register error at {address}: {result}")
                return False
            return True
        except Exception as e:
            self.error_occurred.emit(f"Write register exception: {e}")
            return False

    def read_device_status(self, device: dict) -> bool | None:
        """Read the on/off status of a device."""
        try:
            result = self._client.read_holding_registers(
                address=device["status_register"], count=1, slave=self._unit_id
            )
            if result.isError():
                return None
            return result.registers[0] != 0
        except Exception:
            return None

    def set_device_on(self, device: dict, on: bool) -> bool:
        """Turn a device on or off via its control coil."""
        return self.write_coil(device["control_register"], on)

    def set_device_setpoint(self, device: dict, value: float) -> bool:
        """Write a setpoint value to the device's setpoint register."""
        if device.get("setpoint_register") is None:
            return False
        int_value = max(0, min(65535, int(value)))
        return self.write_register(device["setpoint_register"], int_value)
