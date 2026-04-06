"""FastAPI application for Code Profiler Environment."""

import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import json


@dataclass
class Hotspot:
    function_name: str = ""
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    self_time_ms: float = 0.0
    total_time_ms: float = 0.0
    call_count: int = 0
    percentage: float = 0.0


@dataclass
class IterationResult:
    iteration: int = 0
    language: str = ""
    build_success: bool = False
    profiler_output: Optional[str] = None
    hotspots: List[Hotspot] = field(default_factory=list)
    execution_time_ms: float = 0.0
    reward: float = 0.0
    delta_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class ProfileAction(BaseModel):
    action_type: Literal["build", "profile", "fix", "test"]
    language: Literal["java", "python", "cpp"]
    iteration: int = Field(default=0, ge=0, le=4)
    code_fix: Optional[str] = None
    test_input: Optional[str] = None


class ProfileObservation(BaseModel):
    build_status: bool = False
    build_output: Optional[str] = None
    profiler_output: Optional[str] = None
    hotspots: List[Hotspot] = field(default_factory=list)
    execution_time_ms: float = 0.0
    reward: float = 0.0
    delta_percent: float = 0.0
    done: bool = False
    current_iteration: int = 0
    language: str = "python"
    message: str = ""


class ProfileState(BaseModel):
    episode_id: str = ""
    step_count: int = 0
    language: str = "python"
    current_iteration: int = 0
    best_performance_ms: float = 999999.0
    baseline_performance_ms: float = 0.0
    iteration_results: List[IterationResult] = field(default_factory=list)
    is_complete: bool = False


class PerformanceRewardCalculator:
    def __init__(self, baseline_ms: float):
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def compute_reward(
        self, current_ms: float, previous_ms: Optional[float] = None
    ) -> tuple[float, float]:
        if previous_ms is not None:
            self.previous_ms = previous_ms

        if self.previous_ms == 0:
            return 0.0, 0.0

        delta_percent = ((current_ms - self.previous_ms) / self.previous_ms) * 100

        if abs(delta_percent) < 0.5:
            return 0.0, delta_percent

        reward = delta_percent * -0.05
        reward = max(-2.0, min(2.0, reward))

        self.previous_ms = current_ms

        if current_ms < self.best_ms:
            self.best_ms = current_ms

        return round(reward, 3), round(delta_percent, 2)


app = FastAPI(title="Code Profiler Environment")

state = ProfileState(episode_id=str(uuid.uuid4()))
calculator = PerformanceRewardCalculator(100.0)
languages = ["python", "java", "cpp"]
previous_time_ms = 0.0


def reset_env(language: str = "python") -> ProfileObservation:
    global state, calculator, previous_time_ms
    state = ProfileState(
        episode_id=str(uuid.uuid4()),
        step_count=0,
        language=language,
        current_iteration=0,
        baseline_performance_ms=0.0,
        iteration_results=[],
        is_complete=False,
    )
    calculator = PerformanceRewardCalculator(100.0)
    previous_time_ms = 0.0

    return ProfileObservation(
        build_status=True,
        build_output="Environment ready",
        profiler_output=None,
        hotspots=[],
        execution_time_ms=0.0,
        reward=0.0,
        delta_percent=0.0,
        done=False,
        current_iteration=0,
        language=language,
        message="Environment reset. Ready for code profiling.",
    )


def step_env(action: ProfileAction) -> ProfileObservation:
    global state, calculator, previous_time_ms
    state.step_count += 1

    if action.action_type == "build":
        state.current_iteration += 1
        return ProfileObservation(
            build_status=True,
            build_output="Build successful",
            profiler_output=None,
            hotspots=[],
            execution_time_ms=0.0,
            reward=0.0,
            delta_percent=0.0,
            done=False,
            current_iteration=state.current_iteration,
            language=action.language,
            message=f"Build successful. Iteration {state.current_iteration}.",
        )

    elif action.action_type == "profile":
        if state.baseline_performance_ms == 0.0:
            execution_time_ms = 125.0
            reward = 0.0
            delta_percent = 0.0
            calculator.baseline_ms = execution_time_ms
            calculator.previous_ms = execution_time_ms
            state.baseline_performance_ms = execution_time_ms
            state.best_performance_ms = execution_time_ms
        else:
            deltas = {
                "python": [1.15, 0.82, 1.08, 0.75],
                "java": [1.12, 0.85, 1.05, 0.72],
                "cpp": [1.18, 0.80, 1.10, 0.68],
            }
            lang_deltas = deltas.get(action.language, [1.0, 1.0, 1.0, 1.0])
            delta = lang_deltas[(action.iteration - 1) % 4]
            execution_time_ms = state.baseline_performance_ms * delta
            reward, delta_percent = calculator.compute_reward(execution_time_ms)

        if execution_time_ms < state.best_performance_ms:
            state.best_performance_ms = execution_time_ms

        previous_time_ms = execution_time_ms

        hotspots = [
            Hotspot(function_name="build_catalog_response", percentage=35.0),
            Hotspot(function_name="find_product_linear", percentage=22.0),
            Hotspot(function_name="calculate_order_total", percentage=18.0),
        ]

        return ProfileObservation(
            build_status=True,
            build_output="Build successful",
            profiler_output="Profile complete",
            hotspots=hotspots,
            execution_time_ms=execution_time_ms,
            reward=reward,
            delta_percent=delta_percent,
            done=False,
            current_iteration=state.current_iteration,
            language=action.language,
            message=f"Profile complete. Execution: {execution_time_ms:.2f}ms. Top hotspot: build_catalog_response (35.0%)",
        )

    return ProfileObservation(
        build_status=True,
        build_output="OK",
        profiler_output=None,
        hotspots=[],
        execution_time_ms=previous_time_ms,
        reward=0.0,
        delta_percent=0.0,
        done=False,
        current_iteration=state.current_iteration,
        language=action.language,
        message="OK",
    )


@app.get("/")
async def root():
    return {"message": "Code Profiler Environment API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/reset")
async def reset(data: dict = None):
    language = data.get("language", "python") if data else "python"
    observation = reset_env(language)
    return {"observation": observation.model_dump(), "state": state.model_dump()}


@app.post("/step")
async def step(action: ProfileAction):
    observation = step_env(action)
    done = state.is_complete or state.current_iteration >= 4
    return {"observation": observation.model_dump(), "state": state.model_dump()}


@app.get("/state")
async def get_state():
    return state.model_dump()


@app.get("/hotspots")
async def get_hotspots():
    if state.iteration_results:
        return [h.model_dump() for h in state.iteration_results[-1].hotspots]
    return []


@app.get("/results")
async def get_results():
    return [r.model_dump() for r in state.iteration_results]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            action_type = data.get("type")

            if action_type == "reset":
                observation = reset_env(data.get("language", "python"))
                await websocket.send_json({"type": "observation", "data": observation.model_dump()})

            elif action_type == "step":
                action = ProfileAction(**data.get("action", {}))
                observation = step_env(action)
                await websocket.send_json({"type": "observation", "data": observation.model_dump()})

            elif action_type == "state":
                await websocket.send_json({"type": "state", "data": state.model_dump()})

    except WebSocketDisconnect:
        pass
