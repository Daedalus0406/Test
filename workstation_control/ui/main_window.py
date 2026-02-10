"""
Main application window integrating all workstation control components.

Layout:
┌─────────────────────────────────────────────────────────┐
│  Toolbar: [Connect] [Record] [History] [Status Bar]     │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│   Control Panel      │     Trend Charts                 │
│   (left sidebar)     │     (Temperature / Pressure /    │
│                      │      Flow stacked plots)         │
│                      │                                  │
├──────────────────────┴──────────────────────────────────┤
│  Status bar: connection, recording info, errors         │
└─────────────────────────────────────────────────────────┘
"""

import os
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAction,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.data_recorder import DataRecorder
from core.modbus_client import ModbusClient
from ui.control_panel import ControlPanel
from ui.history_viewer import HistoryViewer
from ui.trend_chart import TrendChart


class MainWindow(QMainWindow):
    """Main application window for workstation control."""

    def __init__(self, config: dict, data_dir: str = "data"):
        super().__init__()
        self._config = config
        self._data_dir = data_dir

        self.setWindowTitle(f"Workstation Control - {config['station_name']}")
        self.setMinimumSize(1200, 800)

        # Create core components
        self._modbus = ModbusClient(config, parent=self)
        self._recorder = DataRecorder(base_dir=data_dir, parent=self)

        # Create UI
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        # Connect signals
        self._connect_signals()

        # Device status polling timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_device_status)

    def _build_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Connection controls
        self._connect_action = QAction("Connect", self)
        self._connect_action.setCheckable(True)
        self._connect_action.triggered.connect(self._on_connect_toggle)
        toolbar.addAction(self._connect_action)

        toolbar.addSeparator()

        # Recording controls
        self._record_action = QAction("Start Recording", self)
        self._record_action.setEnabled(False)
        self._record_action.triggered.connect(self._on_record_toggle)
        toolbar.addAction(self._record_action)

        # Recording duration label
        self._duration_label = QLabel("  00:00:00  ")
        self._duration_label.setStyleSheet(
            "font-family: monospace; font-size: 14px; color: #666; "
            "padding: 0 8px;"
        )
        toolbar.addWidget(self._duration_label)

        toolbar.addSeparator()

        # History viewer
        self._history_action = QAction("History Viewer", self)
        self._history_action.triggered.connect(self._on_history)
        toolbar.addAction(self._history_action)

        toolbar.addSeparator()

        # Clear trends
        self._clear_action = QAction("Clear Trends", self)
        self._clear_action.triggered.connect(self._on_clear_trends)
        toolbar.addAction(self._clear_action)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # Left: Control Panel (scrollable)
        self._control_panel = ControlPanel(
            devices=self._config["devices"],
            sensors=self._config["sensors"],
        )
        self._control_panel.setMinimumWidth(350)
        self._control_panel.setMaximumWidth(500)
        splitter.addWidget(self._control_panel)

        # Right: Trend Charts
        self._trend_chart = TrendChart(
            sensors=self._config["sensors"],
        )
        splitter.addWidget(self._trend_chart)

        splitter.setSizes([380, 800])
        layout.addWidget(splitter)

    def _build_statusbar(self):
        sb = self.statusBar()
        self._conn_status = QLabel("Disconnected")
        self._conn_status.setStyleSheet(
            "color: #F44336; font-weight: bold; padding: 0 12px;"
        )
        sb.addPermanentWidget(self._conn_status)

        self._rec_status = QLabel("")
        self._rec_status.setStyleSheet("padding: 0 12px;")
        sb.addPermanentWidget(self._rec_status)

    def _connect_signals(self):
        # Modbus signals
        self._modbus.data_received.connect(self._on_data_received)
        self._modbus.connection_changed.connect(self._on_connection_changed)
        self._modbus.error_occurred.connect(self._on_error)

        # Control panel signals
        self._control_panel.device_toggle.connect(self._on_device_toggle)
        self._control_panel.device_setpoint.connect(self._on_device_setpoint)

        # Recorder signals
        self._recorder.recording_started.connect(self._on_recording_started)
        self._recorder.recording_stopped.connect(self._on_recording_stopped)
        self._recorder.recording_error.connect(self._on_error)
        self._recorder.duration_updated.connect(self._on_duration_updated)
        self._recorder.auto_stopped.connect(self._on_auto_stopped)

    # ── Action handlers ─────────────────────────────────────────────────

    def _on_connect_toggle(self, checked: bool):
        if checked:
            self.statusBar().showMessage(
                f"Connecting to {self._config['plc']['host']}:"
                f"{self._config['plc']['port']}..."
            )
            if self._modbus.connect():
                self._modbus.start_polling()
                self._status_timer.start(2000)
            else:
                self._connect_action.setChecked(False)
        else:
            self._modbus.disconnect()
            self._status_timer.stop()

    def _on_record_toggle(self):
        if self._recorder.is_recording:
            reply = QMessageBox.question(
                self,
                "Stop Recording",
                "Are you sure you want to stop recording?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._recorder.stop_recording()
        else:
            self._recorder.start_recording()

    def _on_history(self):
        dialog = HistoryViewer(base_dir=self._data_dir, parent=self)
        dialog.exec_()

    def _on_clear_trends(self):
        self._trend_chart.clear_data()

    # ── Data flow ───────────────────────────────────────────────────────

    def _on_data_received(self, readings: list):
        """Handle incoming sensor data from PLC."""
        # Update trend chart
        self._trend_chart.update_data(readings)

        # Update control panel sensor display
        self._control_panel.update_sensor_readings(readings)

        # Record data if recording
        if self._recorder.is_recording:
            self._recorder.append_data(readings)

    def _poll_device_status(self):
        """Periodically read device statuses from PLC."""
        for device in self._config["devices"]:
            status = self._modbus.read_device_status(device)
            if status is not None:
                self._control_panel.update_device_status(device["name"], status)

    # ── Device control ──────────────────────────────────────────────────

    def _on_device_toggle(self, device: dict, state: bool):
        action = "START" if state else "STOP"
        reply = QMessageBox.question(
            self,
            f"{action} {device['name']}",
            f"Are you sure you want to {action} {device['name']}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            success = self._modbus.set_device_on(device, state)
            if success:
                self._control_panel.update_device_status(device["name"], state)
                self.statusBar().showMessage(
                    f"{device['name']} {action} command sent", 3000
                )

    def _on_device_setpoint(self, device: dict, value: float):
        success = self._modbus.set_device_setpoint(device, value)
        if success:
            self.statusBar().showMessage(
                f"{device['name']} setpoint set to {value} {device.get('setpoint_unit', '')}",
                3000,
            )

    # ── Status updates ──────────────────────────────────────────────────

    def _on_connection_changed(self, connected: bool):
        if connected:
            self._conn_status.setText("Connected")
            self._conn_status.setStyleSheet(
                "color: #4CAF50; font-weight: bold; padding: 0 12px;"
            )
            self._connect_action.setText("Disconnect")
            self._record_action.setEnabled(True)
        else:
            self._conn_status.setText("Disconnected")
            self._conn_status.setStyleSheet(
                "color: #F44336; font-weight: bold; padding: 0 12px;"
            )
            self._connect_action.setText("Connect")
            self._connect_action.setChecked(False)
            self._record_action.setEnabled(False)

    def _on_recording_started(self, path: str):
        self._record_action.setText("Stop Recording")
        self._rec_status.setText("Recording...")
        self._rec_status.setStyleSheet(
            "color: #F44336; font-weight: bold; padding: 0 12px;"
        )
        self.statusBar().showMessage(f"Recording started: {path}", 5000)

    def _on_recording_stopped(self, path: str):
        self._record_action.setText("Start Recording")
        self._rec_status.setText("")
        self._duration_label.setText("  00:00:00  ")
        self.statusBar().showMessage(f"Recording saved: {path}", 5000)

    def _on_duration_updated(self, duration_str: str):
        self._duration_label.setText(f"  {duration_str}  ")
        self._duration_label.setStyleSheet(
            "font-family: monospace; font-size: 14px; color: #F44336; "
            "font-weight: bold; padding: 0 8px;"
        )

    def _on_auto_stopped(self):
        QMessageBox.information(
            self,
            "Recording Auto-Stopped",
            "Recording has been automatically stopped after reaching "
            "the 24-hour maximum duration.",
        )

    def _on_error(self, message: str):
        self.statusBar().showMessage(f"Error: {message}", 5000)

    # ── Window lifecycle ────────────────────────────────────────────────

    def closeEvent(self, event):
        """Clean up on application exit."""
        if self._recorder.is_recording:
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "A recording is still in progress. Stop and save before exit?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                self._recorder.stop_recording()

        self._modbus.disconnect()
        event.accept()
