"""
Control panel widget for operating PLC-connected devices.

Dynamically generates control widgets based on the config:
- Pump: ON/OFF toggle + speed setpoint
- Motor: ON/OFF toggle + frequency setpoint
- Heater: ON/OFF toggle + temperature setpoint

Each device card shows its current status and provides controls.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# Icons/labels by device type
DEVICE_STYLE = {
    "pump": {"label": "PUMP", "color_on": "#2196F3", "color_off": "#90CAF9"},
    "motor": {"label": "MOTOR", "color_on": "#4CAF50", "color_off": "#A5D6A7"},
    "heater": {"label": "HEATER", "color_on": "#F44336", "color_off": "#EF9A9A"},
}


class DeviceCard(QFrame):
    """
    A single device control card with ON/OFF toggle and setpoint input.

    Signals:
        toggle_requested(dict, bool): device config, desired state (True=ON)
        setpoint_requested(dict, float): device config, desired setpoint value
    """

    toggle_requested = pyqtSignal(dict, bool)
    setpoint_requested = pyqtSignal(dict, float)

    def __init__(self, device: dict, parent=None):
        super().__init__(parent)
        self._device = device
        self._is_on = False

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumWidth(220)

        self._build_ui()
        self._update_style()

    def _build_ui(self):
        dev = self._device
        style = DEVICE_STYLE.get(dev["type"], DEVICE_STYLE["pump"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Header: type badge + device name
        header = QHBoxLayout()
        self._type_label = QLabel(style["label"])
        self._type_label.setFixedWidth(70)
        self._type_label.setAlignment(Qt.AlignCenter)
        self._type_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; padding: 2px 6px; "
            "border-radius: 3px; color: white; "
            f"background-color: {style['color_off']};"
        )
        header.addWidget(self._type_label)

        name_label = QLabel(dev["name"])
        name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(name_label)
        header.addStretch()

        # Status indicator
        self._status_label = QLabel("OFF")
        self._status_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #999;"
        )
        header.addWidget(self._status_label)
        layout.addLayout(header)

        # Control row
        control_row = QHBoxLayout()

        # ON/OFF toggle button
        self._toggle_btn = QPushButton("START")
        self._toggle_btn.setFixedSize(80, 36)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setStyleSheet(self._button_style(False))
        self._toggle_btn.clicked.connect(self._on_toggle)
        control_row.addWidget(self._toggle_btn)

        # Setpoint input (if device has setpoint register)
        if dev.get("setpoint_register") is not None:
            control_row.addWidget(QLabel(f"Setpoint ({dev.get('setpoint_unit', '')}):"))
            self._setpoint_spin = QDoubleSpinBox()
            self._setpoint_spin.setRange(
                dev.get("setpoint_min", 0), dev.get("setpoint_max", 100)
            )
            self._setpoint_spin.setDecimals(1)
            self._setpoint_spin.setSingleStep(1.0)
            self._setpoint_spin.setFixedWidth(100)
            control_row.addWidget(self._setpoint_spin)

            self._set_btn = QPushButton("SET")
            self._set_btn.setFixedSize(50, 30)
            self._set_btn.clicked.connect(self._on_setpoint)
            self._set_btn.setStyleSheet(
                "QPushButton { background-color: #607D8B; color: white; "
                "border-radius: 4px; font-weight: bold; }"
                "QPushButton:hover { background-color: #455A64; }"
            )
            control_row.addWidget(self._set_btn)
        else:
            self._setpoint_spin = None
            self._set_btn = None

        control_row.addStretch()
        layout.addLayout(control_row)

    def _button_style(self, is_on: bool) -> str:
        if is_on:
            return (
                "QPushButton { background-color: #f44336; color: white; "
                "border-radius: 4px; font-weight: bold; font-size: 13px; }"
                "QPushButton:hover { background-color: #d32f2f; }"
            )
        return (
            "QPushButton { background-color: #4CAF50; color: white; "
            "border-radius: 4px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #388E3C; }"
        )

    def _on_toggle(self):
        desired = not self._is_on
        self.toggle_requested.emit(self._device, desired)

    def _on_setpoint(self):
        if self._setpoint_spin is not None:
            value = self._setpoint_spin.value()
            self.setpoint_requested.emit(self._device, value)

    def set_status(self, is_on: bool):
        """Update the displayed device status."""
        self._is_on = is_on
        self._toggle_btn.setChecked(is_on)
        self._toggle_btn.setText("STOP" if is_on else "START")
        self._toggle_btn.setStyleSheet(self._button_style(is_on))
        self._status_label.setText("ON" if is_on else "OFF")
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; "
            f"color: {'#4CAF50' if is_on else '#999'};"
        )
        self._update_style()

    def _update_style(self):
        style = DEVICE_STYLE.get(self._device["type"], DEVICE_STYLE["pump"])
        color = style["color_on"] if self._is_on else style["color_off"]
        self._type_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; padding: 2px 6px; "
            f"border-radius: 3px; color: white; background-color: {color};"
        )


class ControlPanel(QWidget):
    """
    Panel containing dynamically generated device control cards.

    Also shows live sensor readings in a table-like summary.
    """

    device_toggle = pyqtSignal(dict, bool)
    device_setpoint = pyqtSignal(dict, float)

    def __init__(self, devices: list, sensors: list, parent=None):
        super().__init__(parent)
        self._devices = devices
        self._sensors = sensors
        self._cards = {}         # device_name -> DeviceCard
        self._sensor_labels = {} # tag -> QLabel (for live value display)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Device Controls ──
        dev_group = QGroupBox("Device Controls")
        dev_layout = QVBoxLayout(dev_group)

        for device in self._devices:
            card = DeviceCard(device)
            card.toggle_requested.connect(self._on_toggle)
            card.setpoint_requested.connect(self._on_setpoint)
            self._cards[device["name"]] = card
            dev_layout.addWidget(card)

        dev_layout.addStretch()
        layout.addWidget(dev_group)

        # ── Sensor Readings Summary ──
        sensor_group = QGroupBox("Live Sensor Readings")
        sensor_layout = QGridLayout(sensor_group)
        sensor_layout.setSpacing(6)

        # Headers
        for col, header in enumerate(["Tag", "Name", "Value", "Unit", "Status"]):
            lbl = QLabel(header)
            lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
            sensor_layout.addWidget(lbl, 0, col)

        for row, sensor in enumerate(self._sensors, start=1):
            sensor_layout.addWidget(QLabel(sensor["tag"]), row, 0)
            sensor_layout.addWidget(QLabel(sensor["name"]), row, 1)

            value_lbl = QLabel("---")
            value_lbl.setStyleSheet("font-family: monospace; font-size: 13px;")
            self._sensor_labels[sensor["tag"]] = {
                "value": value_lbl,
                "unit": sensor["unit"],
            }
            sensor_layout.addWidget(value_lbl, row, 2)
            sensor_layout.addWidget(QLabel(sensor["unit"]), row, 3)

            status_lbl = QLabel("--")
            status_lbl.setStyleSheet("font-size: 11px;")
            self._sensor_labels[sensor["tag"]]["status"] = status_lbl
            sensor_layout.addWidget(status_lbl, row, 4)

        layout.addWidget(sensor_group)
        layout.addStretch()

    def _on_toggle(self, device: dict, state: bool):
        self.device_toggle.emit(device, state)

    def _on_setpoint(self, device: dict, value: float):
        self.device_setpoint.emit(device, value)

    def update_device_status(self, device_name: str, is_on: bool):
        """Update the status display of a device card."""
        card = self._cards.get(device_name)
        if card:
            card.set_status(is_on)

    def update_sensor_readings(self, readings: list):
        """Update the live sensor readings display."""
        for reading in readings:
            info = self._sensor_labels.get(reading.tag)
            if info is None:
                continue
            info["value"].setText(f"{reading.value:.2f}")

            if reading.alarm == "HIGH":
                info["status"].setText("HIGH")
                info["status"].setStyleSheet(
                    "font-size: 11px; color: white; background-color: #F44336; "
                    "padding: 1px 4px; border-radius: 2px; font-weight: bold;"
                )
            elif reading.alarm == "LOW":
                info["status"].setText("LOW")
                info["status"].setStyleSheet(
                    "font-size: 11px; color: white; background-color: #FF9800; "
                    "padding: 1px 4px; border-radius: 2px; font-weight: bold;"
                )
            else:
                info["status"].setText("OK")
                info["status"].setStyleSheet(
                    "font-size: 11px; color: #4CAF50; font-weight: bold;"
                )
