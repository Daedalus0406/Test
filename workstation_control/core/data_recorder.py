"""
Data recorder that writes sensor data to Excel files.

Behavior:
- On application start: creates a date-based folder (YYYY-MM-DD)
- On recording start: creates an Excel file with Temperature, Pressure, Flow sheets
- Continuously appends data rows each polling cycle (1-second intervals)
- Maximum recording duration: 24 hours
- On recording stop: renames the file to "starttime_endtime.xlsx" (hhmmss format)
"""

import os
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, pyqtSignal
from openpyxl import Workbook


# Maximum recording duration
MAX_RECORDING_DURATION = timedelta(hours=24)

# Sheet names mapped to sensor categories
CATEGORY_SHEETS = {
    "Temperature": "Temperature",
    "Pressure": "Pressure",
    "Flow": "Flow",
}


class DataRecorder(QObject):
    """
    Records sensor data into Excel files organized by date folders.

    Signals:
        recording_started(str): Emitted with the temp file path when recording begins.
        recording_stopped(str): Emitted with the final file path when recording stops.
        recording_error(str): Emitted on errors during recording.
        duration_updated(str): Emitted with current recording duration "HH:MM:SS".
        auto_stopped(): Emitted when recording auto-stops at 24h limit.
    """

    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    recording_error = pyqtSignal(str)
    duration_updated = pyqtSignal(str)
    auto_stopped = pyqtSignal()

    def __init__(self, base_dir: str = ".", parent=None):
        super().__init__(parent)
        self._base_dir = base_dir
        self._is_recording = False
        self._workbook = None
        self._sheets = {}
        self._temp_path = None
        self._start_time = None
        self._row_counts = {}

        # Ensure today's date folder exists
        self._date_folder = self._ensure_date_folder()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def date_folder(self) -> str:
        return self._date_folder

    def _ensure_date_folder(self) -> str:
        """Create and return today's date folder."""
        today = datetime.now().strftime("%Y-%m-%d")
        folder = os.path.join(self._base_dir, today)
        os.makedirs(folder, exist_ok=True)
        return folder

    def start_recording(self) -> bool:
        """Start a new recording session."""
        if self._is_recording:
            self.recording_error.emit("Recording is already in progress.")
            return False

        try:
            self._start_time = datetime.now()

            # Create workbook with category sheets
            self._workbook = Workbook()
            # Remove default sheet
            default_sheet = self._workbook.active
            self._workbook.remove(default_sheet)

            for category, sheet_name in CATEGORY_SHEETS.items():
                ws = self._workbook.create_sheet(title=sheet_name)
                ws.append(["Tag", "Time", "Value", "Unit"])
                # Set column widths
                ws.column_dimensions["A"].width = 15
                ws.column_dimensions["B"].width = 12
                ws.column_dimensions["C"].width = 15
                ws.column_dimensions["D"].width = 10
                self._sheets[category] = ws
                self._row_counts[category] = 1  # Header row

            # Save as temporary file
            self._temp_path = os.path.join(
                self._date_folder, "_recording_in_progress.xlsx"
            )
            self._workbook.save(self._temp_path)
            self._is_recording = True
            self.recording_started.emit(self._temp_path)
            return True

        except Exception as e:
            self.recording_error.emit(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> str | None:
        """Stop recording and rename the file with start_end timestamps."""
        if not self._is_recording:
            return None

        try:
            end_time = datetime.now()
            self._is_recording = False

            # Save final data
            self._workbook.save(self._temp_path)

            # Build final filename: starttime_endtime.xlsx
            start_str = self._start_time.strftime("%H%M%S")
            end_str = end_time.strftime("%H%M%S")
            final_name = f"{start_str}_{end_str}.xlsx"
            final_path = os.path.join(self._date_folder, final_name)

            # Handle name collision
            counter = 1
            while os.path.exists(final_path):
                final_name = f"{start_str}_{end_str}_{counter}.xlsx"
                final_path = os.path.join(self._date_folder, final_name)
                counter += 1

            os.rename(self._temp_path, final_path)

            self._workbook = None
            self._sheets.clear()
            self._temp_path = None

            self.recording_stopped.emit(final_path)
            return final_path

        except Exception as e:
            self.recording_error.emit(f"Failed to stop recording: {e}")
            return None

    def append_data(self, readings: list):
        """
        Append sensor readings to the appropriate Excel sheets.

        Args:
            readings: list of SensorReading objects
        """
        if not self._is_recording or self._workbook is None:
            return

        # Check 24-hour limit
        elapsed = datetime.now() - self._start_time
        if elapsed >= MAX_RECORDING_DURATION:
            self.stop_recording()
            self.auto_stopped.emit()
            return

        # Emit duration update
        total_seconds = int(elapsed.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        self.duration_updated.emit(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        for reading in readings:
            category = reading.category
            ws = self._sheets.get(category)
            if ws is None:
                continue

            ws.append([
                reading.tag,
                reading.timestamp,
                round(reading.value, 4),
                reading.unit,
            ])
            self._row_counts[category] = self._row_counts.get(category, 0) + 1

        # Periodic save (every 60 rows of data ~ 1 minute)
        total_rows = sum(self._row_counts.values())
        if total_rows % 60 == 0:
            try:
                self._workbook.save(self._temp_path)
            except Exception as e:
                self.recording_error.emit(f"Auto-save error: {e}")

    def get_recording_info(self) -> dict | None:
        """Get information about the current recording session."""
        if not self._is_recording:
            return None

        elapsed = datetime.now() - self._start_time
        return {
            "start_time": self._start_time.strftime("%H:%M:%S"),
            "elapsed": str(elapsed).split(".")[0],
            "rows": dict(self._row_counts),
            "file": self._temp_path,
        }
