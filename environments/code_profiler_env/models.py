"""Type-safe models for Code Profiler Environment - Hackathon Ready."""

from typing import Literal, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class TaskDifficulty(str, Enum):
    """Task difficulty levels for grading."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TaskType(str, Enum):
    """Types of profiling tasks."""
    STRING_CONCATENATION = "string_concatenation"
    LINEAR_SEARCH = "linear_search"
    MEMORY_OPTIMIZATION = "memory_optimization"


class GradingCriteria(BaseModel):
    """Grading criteria for a task."""
    metric: str = Field(description="Metric being graded (e.g., execution_time, memory_usage)")
    target: float = Field(description="Target value for full score")
    threshold: float = Field(description="Acceptable threshold")
    weight: float = Field(default=1.0, description="Weight of this metric in overall score")


class Task(BaseModel):
    """Definition of a profiling task."""
    task_id: str = Field(description="Unique task identifier")
    name: str = Field(description="Human-readable task name")
    description: str = Field(description="Detailed task description")
    difficulty: TaskDifficulty = Field(description="Task difficulty level")
    task_type: TaskType = Field(description="Type of optimization required")
    target_language: Literal["python", "java", "cpp", "any"] = Field(default="any")
    max_iterations: int = Field(default=5, description="Maximum iterations allowed")
    grading_criteria: List[GradingCriteria] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list, description="Optional hints for the agent")


class Hotspot(BaseModel):
    """Represents a performance hotspot identified by profiler."""
    function_name: str = Field(description="Name of the function with hotspot")
    file_path: Optional[str] = Field(default=None, description="File containing the hotspot")
    line_number: Optional[int] = Field(default=None, description="Line number of hotspot")
    self_time_ms: float = Field(default=0.0, description="Self time in milliseconds")
    total_time_ms: float = Field(default=0.0, description="Total time including children")
    call_count: int = Field(default=0, description="Number of times this function was called")
    percentage: float = Field(default=0.0, description="Percentage of total execution time")


class IterationResult(BaseModel):
    """Results from a single profiling iteration."""
    iteration: int = Field(ge=0, le=5)
    language: str = Field(description="Programming language: java, python, or cpp")
    build_success: bool = Field(default=False, description="Whether build succeeded")
    profiler_output: Optional[str] = Field(default=None, description="Raw profiler output")
    hotspots: List[Hotspot] = Field(default_factory=list, description="Identified hotspots")
    execution_time_ms: float = Field(default=0.0, description="Average execution time in milliseconds")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    reward: float = Field(default=0.0, description="Step reward (normalized 0.0-1.0)")
    cumulative_score: float = Field(default=0.0, description="Cumulative task score (0.0-1.0)")
    delta_percent: float = Field(default=0.0, description="Percentage change from baseline")
    fix_applied: Optional[str] = Field(default=None, description="Description of fix applied")
    timestamp: datetime = Field(default_factory=datetime.now)


class ProfileAction(BaseModel):
    """Actions that can be taken in the code profiler environment."""
    action_type: Literal["build", "profile", "fix", "test", "submit"] = Field(
        description="Type of action to perform"
    )
    language: Literal["python", "java", "cpp"] = Field(description="Target programming language")
    iteration: int = Field(default=0, ge=0, le=5, description="Current iteration (0-5)")
    code_fix: Optional[str] = Field(default=None, description="Code fix to apply (for fix action)")
    test_input: Optional[str] = Field(
        default=None, description="Test input for profiling (for profile action)"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Agent's reasoning for the action"
    )


class ProfileObservation(BaseModel):
    """Observation returned after each step."""
    build_status: bool = Field(default=False, description="Whether the build succeeded")
    build_output: Optional[str] = Field(default=None, description="Build output/error messages")
    profiler_output: Optional[str] = Field(default=None, description="Raw profiler output")
    hotspots: List[Hotspot] = Field(default_factory=list, description="Identified performance hotspots")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    reward: float = Field(default=0.0, description="Step reward (normalized 0.0-1.0)")
    cumulative_score: float = Field(default=0.0, description="Cumulative task score (0.0-1.0)")
    delta_percent: float = Field(default=0.0, description="Percentage change from baseline")
    done: bool = Field(default=False, description="Whether episode is complete")
    current_iteration: int = Field(default=0, description="Current iteration number")
    max_iterations: int = Field(default=5, description="Maximum iterations allowed")
    language: str = Field(default="python", description="Current language being profiled")
    task: Optional[Task] = Field(default=None, description="Current task definition")
    message: str = Field(default="", description="Human-readable status message")
    error: Optional[str] = Field(default=None, description="Error message if any")


class GraderResult(BaseModel):
    """Result from the grading function."""
    score: float = Field(ge=0.0, le=1.0, description="Normalized score (0.0-1.0)")
    passed: bool = Field(description="Whether task passed")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Detailed metrics")
    feedback: str = Field(default="", description="Grader feedback")
    breakdown: List[Dict[str, Any]] = Field(default_factory=list, description="Score breakdown by criteria")


class ProfileState(BaseModel):
    """State of the environment."""
    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_count: int = Field(default=0, description="Number of steps taken")
    language: str = Field(default="python", description="Current language")
    current_task: Optional[Task] = Field(default=None, description="Current task")
    current_iteration: int = Field(default=0, ge=0, le=5)
    baseline_performance_ms: float = Field(default=0.0, description="Baseline performance")
    best_performance_ms: float = Field(default=float("inf"), description="Best execution time seen")
    baseline_memory_mb: float = Field(default=0.0, description="Baseline memory usage")
    best_memory_mb: float = Field(default=float("inf"), description="Best memory usage")
    iteration_results: List[IterationResult] = Field(default_factory=list)
    is_complete: bool = Field(default=False)
    final_score: float = Field(default=0.0, description="Final task score (0.0-1.0)")


class StepResult(BaseModel):
    """Combined result from a step operation."""
    observation: ProfileObservation
    state: ProfileState
    grader_result: Optional[GraderResult] = None


class ResetResponse(BaseModel):
    """Response from reset endpoint."""
    observation: ProfileObservation
    state: ProfileState
    available_tasks: List[Task] = Field(default_factory=list, description="All available tasks")


AVAILABLE_TASKS = [
    Task(
        task_id="python-string-concat-easy",
        name="Fix String Concatenation (Python)",
        description="The e-commerce API has string concatenation in loops causing slow responses. "
                    "Fix the build_catalog_response function to use efficient string building.",
        difficulty=TaskDifficulty.EASY,
        task_type=TaskType.STRING_CONCATENATION,
        target_language="python",
        max_iterations=3,
        grading_criteria=[
            GradingCriteria(metric="execution_time", target=50.0, threshold=80.0, weight=0.7),
            GradingCriteria(metric="delta_percent", target=-50.0, threshold=-20.0, weight=0.3),
        ],
        hints=[
            "Use string join() or f-strings instead of + operator in loops",
            "Pre-allocate string builder if using manual concatenation",
        ]
    ),
    Task(
        task_id="python-linear-search-medium",
        name="Fix Linear Search (Python)",
        description="The product search uses O(n) linear search. Optimize find_product_by_id_linear "
                    "to use dictionary/hash lookup for O(1) access.",
        difficulty=TaskDifficulty.MEDIUM,
        task_type=TaskType.LINEAR_SEARCH,
        target_language="python",
        max_iterations=4,
        grading_criteria=[
            GradingCriteria(metric="execution_time", target=30.0, threshold=60.0, weight=0.6),
            GradingCriteria(metric="hotspot_reduction", target=80.0, threshold=50.0, weight=0.4),
        ],
        hints=[
            "Use a dictionary to cache products by ID",
            "Build index on first access, then O(1) lookups",
        ]
    ),
    Task(
        task_id="cpp-memory-optimization-hard",
        name="Fix Memory Optimization (C++)",
        description="The C++ implementation has memory allocation issues and excessive copies. "
                    "Optimize to reduce memory churn and improve cache locality.",
        difficulty=TaskDifficulty.HARD,
        task_type=TaskType.MEMORY_OPTIMIZATION,
        target_language="cpp",
        max_iterations=5,
        grading_criteria=[
            GradingCriteria(metric="execution_time", target=20.0, threshold=40.0, weight=0.4),
            GradingCriteria(metric="memory_usage", target=50.0, threshold=100.0, weight=0.4),
            GradingCriteria(metric="hotspot_reduction", target=70.0, threshold=40.0, weight=0.2),
        ],
        hints=[
            "Use move semantics to avoid copies",
            "Pre-allocate vectors instead of push_back in loops",
            "Consider using string_view instead of string copies",
        ]
    ),
]

TASK_MAP = {task.task_id: task for task in AVAILABLE_TASKS}
