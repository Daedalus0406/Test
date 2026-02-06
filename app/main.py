from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

from .config import StationConfig
from .data_sources import build_data_source
from .recorder import Recorder

CONFIG_PATH = Path("config.json")

app = FastAPI(title="Workstation Recorder")


class AppState:
    def __init__(self) -> None:
        self.config = StationConfig.load(CONFIG_PATH)
        self.data_source = build_data_source(self.config.data_source)
        self.recorder = Recorder(self.config, self.data_source)
        self.task: asyncio.Task | None = None


state = AppState()


@app.on_event("startup")
async def startup_event() -> None:
    state.task = asyncio.create_task(state.recorder.loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if state.task:
        state.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state.task


@app.get("/status")
async def status() -> Dict[str, Any]:
    recording = state.recorder.state
    return {
        "recording": recording.is_recording,
        "start_time": recording.start_time.isoformat() if recording.start_time else None,
        "active_file": recording.active_file,
    }


@app.post("/start")
async def start_recording() -> Dict[str, Any]:
    await state.recorder.start()
    return {"status": "started"}


@app.post("/stop")
async def stop_recording() -> Dict[str, Any]:
    final_path = await state.recorder.stop()
    if not final_path:
        raise HTTPException(status_code=400, detail="Recording is not active")
    return {"status": "stopped", "file": final_path}


@app.get("/config")
async def get_config() -> Dict[str, Any]:
    return state.config.model_dump()


@app.get("/history")
async def history() -> Dict[str, Any]:
    base_path = state.config.storage.base_path
    if not base_path.exists():
        return {"folders": []}
    folders = []
    for folder in sorted(base_path.iterdir()):
        if not folder.is_dir():
            continue
        files = [file.name for file in sorted(folder.glob("*.xlsx"))]
        folders.append({"date": folder.name, "files": files})
    return {"folders": folders}
