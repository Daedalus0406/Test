from datetime import datetime

from app.storage import (
    _ensure_workbook,
    append_rows,
    create_recording_paths,
    finalize_recording,
)
from app.data_sources import SensorSample


def test_create_recording_paths(tmp_path):
    timestamp = datetime(2024, 1, 2, 3, 4, 5)
    paths = create_recording_paths(tmp_path, timestamp)

    assert paths.folder.exists()
    assert paths.folder.name == "2024-01-02"
    assert paths.active_file.name == "recording.xlsx"


def test_workbook_lifecycle(tmp_path):
    workbook_path = tmp_path / "recording.xlsx"
    sheet_names = ["Temperature", "Pressure", "Flow rate"]

    _ensure_workbook(workbook_path, sheet_names)
    assert workbook_path.exists()

    rows_by_sheet = {
        "Temperature": [
            SensorSample(tag="Temp_1", timestamp=datetime(2024, 1, 1, 8, 0, 0), value=12.3)
        ],
        "Pressure": [
            SensorSample(tag="Pressure_1", timestamp=datetime(2024, 1, 1, 8, 0, 1), value=45.6)
        ],
        "Flow rate": [
            SensorSample(tag="Flow_1", timestamp=datetime(2024, 1, 1, 8, 0, 2), value=7.8)
        ],
    }
    append_rows(workbook_path, rows_by_sheet)

    final_path = finalize_recording(
        workbook_path,
        start_time=datetime(2024, 1, 1, 8, 0, 0),
        end_time=datetime(2024, 1, 1, 9, 0, 0),
    )

    assert final_path.exists()
    assert final_path.name == "080000_090000.xlsx"
