from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class DataSourceConfig(BaseModel):
    kind: str = Field("mock", description="mock or modbus")
    modbus_host: str | None = None
    modbus_port: int = 502


class SheetConfig(BaseModel):
    name: str
    tags: List[str]


class RecordingConfig(BaseModel):
    polling_interval_seconds: float = 1.0
    flush_interval_seconds: float = 5.0
    max_recording_hours: float = 24.0


class StorageConfig(BaseModel):
    base_path: Path = Path("data")


class StationConfig(BaseModel):
    station_id: str
    data_source: DataSourceConfig = DataSourceConfig()
    recording: RecordingConfig = RecordingConfig()
    storage: StorageConfig = StorageConfig()
    sheets: List[SheetConfig]

    @staticmethod
    def load(path: Path) -> "StationConfig":
        return StationConfig.model_validate_json(path.read_text(encoding="utf-8"))

    def sheet_map(self) -> Dict[str, SheetConfig]:
        return {sheet.name: sheet for sheet in self.sheets}
