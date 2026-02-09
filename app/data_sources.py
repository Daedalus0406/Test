from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from .config import DataSourceConfig, SheetConfig


@dataclass
class SensorSample:
    tag: str
    timestamp: datetime
    value: float


class DataSource:
    def read(self, sheet: SheetConfig) -> Dict[str, SensorSample]:
        raise NotImplementedError


class MockDataSource(DataSource):
    def read(self, sheet: SheetConfig) -> Dict[str, SensorSample]:
        now = datetime.now()
        samples: Dict[str, SensorSample] = {}
        for tag in sheet.tags:
            samples[tag] = SensorSample(tag=tag, timestamp=now, value=random.uniform(0, 100))
        return samples


class ModbusDataSource(DataSource):
    def __init__(self, config: DataSourceConfig) -> None:
        if not config.modbus_host:
            raise ValueError("modbus_host must be set when using modbus data source")
        self._config = config

    def read(self, sheet: SheetConfig) -> Dict[str, SensorSample]:
        raise NotImplementedError(
            "Modbus integration is not implemented yet. Use mock data source or extend this class."
        )


def build_data_source(config: DataSourceConfig) -> DataSource:
    kind = config.kind.lower()
    if kind == "mock":
        return MockDataSource()
    if kind == "modbus":
        return ModbusDataSource(config)
    raise ValueError(f"Unknown data source kind: {config.kind}")
