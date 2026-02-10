"""
Real-time trend chart widget using pyqtgraph.

Displays live sensor data in three stacked plots:
- Temperature
- Pressure
- Flow Rate

Each plot auto-scrolls and shows the most recent data window (configurable).
"""

from collections import defaultdict, deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# Color palette for multiple traces per category
COLORS = [
    "#2196F3",  # Blue
    "#F44336",  # Red
    "#4CAF50",  # Green
    "#FF9800",  # Orange
    "#9C27B0",  # Purple
    "#00BCD4",  # Cyan
    "#FFEB3B",  # Yellow
    "#E91E63",  # Pink
]

# Display window options (seconds)
WINDOW_OPTIONS = {
    "1 min": 60,
    "5 min": 300,
    "10 min": 600,
    "30 min": 1800,
    "1 hour": 3600,
}

DEFAULT_WINDOW = 300  # 5 minutes


class TrendChart(QWidget):
    """
    Widget containing three stacked real-time trend plots for
    Temperature, Pressure, and Flow sensor categories.
    """

    def __init__(self, sensors: list, parent=None):
        super().__init__(parent)
        self._sensors = sensors
        self._window_seconds = DEFAULT_WINDOW
        self._tick_counter = 0

        # Data buffers: tag -> deque of (time_index, value)
        self._data = defaultdict(lambda: deque(maxlen=86400))  # max 24h at 1s

        # Organize sensors by category
        self._by_category = defaultdict(list)
        for s in sensors:
            self._by_category[s["category"]].append(s)

        self._plots = {}   # category -> PlotWidget
        self._curves = {}  # tag -> PlotDataItem

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Time Window:"))
        self._window_combo = QComboBox()
        for label in WINDOW_OPTIONS:
            self._window_combo.addItem(label)
        self._window_combo.setCurrentText("5 min")
        self._window_combo.currentTextChanged.connect(self._on_window_changed)
        toolbar.addWidget(self._window_combo)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Configure pyqtgraph appearance
        pg.setConfigOptions(antialias=True, background="w", foreground="k")

        # Create one plot per category
        categories = ["Temperature", "Pressure", "Flow"]
        for cat in categories:
            sensors_in_cat = self._by_category.get(cat, [])
            plot_widget = pg.PlotWidget(title=cat)
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setLabel("left", cat, units=self._get_unit(sensors_in_cat))
            plot_widget.setLabel("bottom", "Time", units="s")
            plot_widget.addLegend(offset=(10, 10))
            plot_widget.setMinimumHeight(180)

            # Create a curve for each sensor in this category
            for idx, sensor in enumerate(sensors_in_cat):
                color = COLORS[idx % len(COLORS)]
                pen = pg.mkPen(color=color, width=2)
                curve = plot_widget.plot(
                    [], [], pen=pen, name=f"{sensor['tag']} ({sensor['name']})"
                )
                self._curves[sensor["tag"]] = curve

            self._plots[cat] = plot_widget
            layout.addWidget(plot_widget)

        # Link X axes for synchronized scrolling
        plot_list = list(self._plots.values())
        if len(plot_list) > 1:
            for p in plot_list[1:]:
                p.setXLink(plot_list[0])

    def _get_unit(self, sensors: list) -> str:
        if sensors:
            return sensors[0].get("unit", "")
        return ""

    def _on_window_changed(self, text: str):
        self._window_seconds = WINDOW_OPTIONS.get(text, DEFAULT_WINDOW)
        self._update_x_range()

    def update_data(self, readings: list):
        """
        Receive new sensor readings and update the trend curves.

        Args:
            readings: list of SensorReading objects
        """
        self._tick_counter += 1

        for reading in readings:
            tag = reading.tag
            self._data[tag].append((self._tick_counter, reading.value))

        # Update curve data
        for reading in readings:
            tag = reading.tag
            curve = self._curves.get(tag)
            if curve is None:
                continue
            buf = self._data[tag]
            if len(buf) == 0:
                continue
            times = [pt[0] for pt in buf]
            values = [pt[1] for pt in buf]
            curve.setData(times, values)

        self._update_x_range()

    def _update_x_range(self):
        """Scroll the X axis to show the most recent time window."""
        x_max = self._tick_counter
        x_min = max(0, x_max - self._window_seconds)
        for plot in self._plots.values():
            plot.setXRange(x_min, x_max, padding=0.02)

    def clear_data(self):
        """Clear all trend data and reset."""
        self._tick_counter = 0
        self._data.clear()
        for curve in self._curves.values():
            curve.setData([], [])
