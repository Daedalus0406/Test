from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from .config import StationConfig
from .data_sources import DataSource, SensorSample
from .storage import append_rows, create_recording_paths, finalize_recording, _ensure_workbook


@dataclass
class RecordingState:
    is_recording: bool = False
    start_time: datetime | None = None
    last_flush_time: datetime | None = None
    active_file: str | None = None
    rows: Dict[str, List[SensorSample]] = field(default_factory=dict)


class Recorder:
    def __init__(
        self,
        config: StationConfig,
        data_source: DataSource,
    ) -> None:
        self._config = config
        self._data_source = data_source
        self._state = RecordingState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> RecordingState:
        return self._state

    async def start(self) -> None:
        async with self._lock:
            if self._state.is_recording:
                return
            now = datetime.now()
            paths = create_recording_paths(self._config.storage.base_path, now)
            _ensure_workbook(paths.active_file, [sheet.name for sheet in self._config.sheets])
            self._state.is_recording = True
            self._state.start_time = now
            self._state.last_flush_time = now
            self._state.active_file = str(paths.active_file)
            self._state.rows = {sheet.name: [] for sheet in self._config.sheets}

    async def stop(self) -> str | None:
        async with self._lock:
            if not self._state.is_recording:
                return None
            await self._flush_locked()
            end_time = datetime.now()
            active_file = self._state.active_file
            start_time = self._state.start_time
            self._state = RecordingState()

        if active_file and start_time:
            final_path = finalize_recording(
                active_file=Path(active_file),
                start_time=start_time,
                end_time=end_time,
            )
            return str(final_path)
        return None

    async def poll_and_buffer(self) -> None:
        async with self._lock:
            if not self._state.is_recording:
                return
            for sheet in self._config.sheets:
                samples = self._data_source.read(sheet)
                self._state.rows[sheet.name].extend(samples.values())

    async def flush_if_needed(self) -> None:
        async with self._lock:
            if not self._state.is_recording:
                return
            now = datetime.now()
            last_flush = self._state.last_flush_time or now
            if (now - last_flush).total_seconds() < self._config.recording.flush_interval_seconds:
                return
            await self._flush_locked()

    async def enforce_limit(self) -> bool:
        async with self._lock:
            if not self._state.is_recording or not self._state.start_time:
                return False
            limit = timedelta(hours=self._config.recording.max_recording_hours)
            if datetime.now() - self._state.start_time >= limit:
                return True
            return False

    async def _flush_locked(self) -> None:
        if not self._state.active_file:
            return
        if not any(self._state.rows.values()):
            self._state.last_flush_time = datetime.now()
            return
        rows_copy = {name: list(rows) for name, rows in self._state.rows.items()}
        for rows in self._state.rows.values():
            rows.clear()
        append_rows(Path(self._state.active_file), rows_copy)
        self._state.last_flush_time = datetime.now()

    async def loop(self) -> None:
        while True:
            await self.poll_and_buffer()
            await self.flush_if_needed()
            if await self.enforce_limit():
                await self.stop()
            await asyncio.sleep(self._config.recording.polling_interval_seconds)
