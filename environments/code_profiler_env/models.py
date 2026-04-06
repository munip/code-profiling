"""Type-safe models for Code Profiler Environment."""

from typing import Literal, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Hotspot(BaseModel):
    """Represents a performance hotspot identified by profiler."""

    function_name: str = Field(description="Name of the function with hotspot")
    file_path: Optional[str] = Field(default=None, description="File containing the hotspot")
    line_number: Optional[int] = Field(default=None, description="Line number of hotspot")
    self_time_ms: float = Field(description="Self time in milliseconds")
    total_time_ms: float = Field(description="Total time including children")
    call_count: int = Field(default=0, description="Number of times this function was called")
    percentage: float = Field(description="Percentage of total execution time")


class IterationResult(BaseModel):
    """Results from a single profiling iteration."""

    iteration: int = Field(ge=0, le=4)
    language: str = Field(description="Programming language: java, python, or cpp")
    build_success: bool = Field(description="Whether build succeeded")
    profiler_output: Optional[str] = Field(default=None, description="Raw profiler output")
    hotspots: List[Hotspot] = Field(default_factory=list, description="Identified hotspots")
    execution_time_ms: float = Field(description="Average execution time in milliseconds")
    reward: float = Field(description="Reward for this iteration (graded % improvement)")
    delta_percent: float = Field(description="Percentage change from previous iteration")
    fix_applied: Optional[str] = Field(default=None, description="Description of fix applied")
    timestamp: datetime = Field(default_factory=datetime.now)


class ProfileAction(BaseModel):
    """Actions that can be taken in the code profiler environment."""

    action_type: Literal["build", "profile", "fix", "test"] = Field(
        description="Type of action to perform"
    )
    language: Literal["java", "python", "cpp"] = Field(description="Target programming language")
    iteration: int = Field(default=0, ge=0, le=4, description="Current iteration (0-4)")
    code_fix: Optional[str] = Field(default=None, description="Code fix to apply (for fix action)")
    test_input: Optional[str] = Field(
        default=None, description="Test input for profiling (for profile action)"
    )


class ProfileObservation(BaseModel):
    """Observation returned after each step."""

    build_status: bool = Field(description="Whether the build succeeded")
    build_output: Optional[str] = Field(default=None, description="Build output/error messages")
    profiler_output: Optional[str] = Field(default=None, description="Raw profiler output")
    hotspots: List[Hotspot] = Field(
        default_factory=list, description="Identified performance hotspots"
    )
    execution_time_ms: float = Field(description="Execution time in milliseconds")
    reward: float = Field(description="Graded reward based on % improvement/degradation")
    delta_percent: float = Field(description="Percentage change from previous iteration")
    done: bool = Field(description="Whether episode is complete")
    current_iteration: int = Field(description="Current iteration number")
    language: str = Field(description="Current language being profiled")
    message: str = Field(default="", description="Human-readable status message")


class ProfileState(BaseModel):
    """State of the environment."""

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_count: int = Field(default=0, description="Number of steps taken")
    language: str = Field(default="python", description="Current language")
    current_iteration: int = Field(default=0, ge=0, le=4)
    best_performance_ms: float = Field(default=float("inf"), description="Best execution time seen")
    baseline_performance_ms: float = Field(
        default=0.0, description="Baseline performance from iteration 0"
    )
    iteration_results: List[IterationResult] = Field(default_factory=list)
    is_complete: bool = Field(default=False)


class StepResult(BaseModel):
    """Combined result from a step operation."""

    observation: ProfileObservation
    state: ProfileState
