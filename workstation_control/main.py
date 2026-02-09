#!/usr/bin/env python3
"""
Workstation Control Interface

An integrated application for controlling PLC-connected workstation devices
with real-time trend charts and data recording capabilities.

Usage:
    python main.py                              # Launch with config selector
    python main.py -c config/station_2pumps.json  # Launch with specific config
    python main.py --simulate                    # Launch in simulation mode (no PLC)

Replaces: Node-RED + InfluxDB solution
Communication: Ethernet / Modbus TCP
Data Storage: Excel files (organized by date folders)
Configuration: JSON config files
"""

import argparse
import os
import sys

from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.config_loader import ConfigError, load_config
from ui.main_window import MainWindow


def select_config() -> str | None:
    """Show a file dialog to let the user pick a config JSON file."""
    path, _ = QFileDialog.getOpenFileName(
        None,
        "Select Workstation Config",
        os.path.join(os.path.dirname(__file__), "config"),
        "JSON Files (*.json)",
    )
    return path if path else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Workstation Control Interface"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to the workstation config JSON file",
    )
    parser.add_argument(
        "-d", "--data-dir",
        type=str,
        default="data",
        help="Base directory for recorded data (default: data)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode (generates fake PLC data)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Select config file
    config_path = args.config
    if config_path is None:
        config_path = select_config()
        if config_path is None:
            sys.exit(0)

    # Load and validate config
    try:
        config = load_config(config_path)
    except ConfigError as e:
        QMessageBox.critical(None, "Config Error", str(e))
        sys.exit(1)
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Failed to load config:\n{e}")
        sys.exit(1)

    # If simulation mode, swap in the simulated Modbus client
    if args.simulate:
        _patch_simulation(config)

    # Ensure data directory exists
    os.makedirs(args.data_dir, exist_ok=True)

    # Launch main window
    window = MainWindow(config=config, data_dir=args.data_dir)
    window.show()

    sys.exit(app.exec_())


def _patch_simulation(config: dict):
    """
    Patch the ModbusClient with a simulated version for testing
    without a real PLC connection.
    """
    import math
    import random
    from datetime import datetime

    from PyQt5.QtCore import QTimer

    from core.modbus_client import ModbusClient, SensorReading

    _original_connect = ModbusClient.connect
    _original_start = ModbusClient.start_polling
    _original_disconnect = ModbusClient.disconnect

    _sim_tick = [0]

    def _sim_connect(self):
        self._connected = True
        self.connection_changed.emit(True)
        return True

    def _sim_start(self):
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(lambda: _sim_poll(self))
        self._poll_timer.start(self._poll_interval)

    def _sim_disconnect(self):
        if hasattr(self, '_poll_timer') and self._poll_timer.isActive():
            self._poll_timer.stop()
        self._connected = False
        self.connection_changed.emit(False)

    def _sim_poll(client):
        _sim_tick[0] += 1
        t = _sim_tick[0]
        now = datetime.now().strftime("%H:%M:%S")
        readings = []

        for sensor in client._sensors:
            base = _get_sim_base(sensor)
            noise = random.gauss(0, base * 0.02)
            wave = math.sin(t * 0.05) * base * 0.1
            value = base + noise + wave
            value = value * sensor.get("scale", 1.0) + sensor.get("offset", 0.0)

            alarm = None
            ah = sensor.get("alarm_high")
            al = sensor.get("alarm_low")
            if ah is not None and value >= ah:
                alarm = "HIGH"
            elif al is not None and value <= al:
                alarm = "LOW"

            readings.append(SensorReading(
                tag=sensor["tag"],
                name=sensor["name"],
                category=sensor["category"],
                value=round(value, 2),
                unit=sensor["unit"],
                timestamp=now,
                alarm=alarm,
            ))

        client.data_received.emit(readings)

    def _get_sim_base(sensor):
        cat = sensor["category"]
        if cat == "Temperature":
            return 450  # raw value; scale 0.1 -> 45°C
        elif cat == "Pressure":
            return 350  # raw value; scale 0.01 -> 3.5 bar
        elif cat == "Flow":
            return 120  # raw value; scale 0.1 -> 12 L/min
        return 100

    def _sim_device_status(self, device):
        return False

    def _sim_set_on(self, device, on):
        return True

    def _sim_set_sp(self, device, value):
        return True

    ModbusClient.connect = _sim_connect
    ModbusClient.start_polling = _sim_start
    ModbusClient.disconnect = _sim_disconnect
    ModbusClient.read_device_status = _sim_device_status
    ModbusClient.set_device_on = _sim_set_on
    ModbusClient.set_device_setpoint = _sim_set_sp


if __name__ == "__main__":
    main()
