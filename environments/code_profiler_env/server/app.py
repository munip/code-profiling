"""FastAPI application for Code Profiler Environment - Hackathon Ready."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional, Any

from dataclasses import dataclass, field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from models import (
    AVAILABLE_TASKS,
    TASK_MAP,
    GraderResult,
    GradingCriteria,
    Hotspot,
    IterationResult,
    ProfileAction,
    ProfileObservation,
    ProfileState,
    ResetResponse,
    StepResult,
    Task,
    TaskDifficulty,
    TaskType,
)


class PerformanceGrader:
    """Grader for profiling tasks that outputs normalized scores (0.0-1.0)."""

    @staticmethod
    def grade_task(
        task: Task,
        baseline_ms: float,
        current_ms: float,
        baseline_memory: float,
        current_memory: float,
        hotspots: List[Hotspot],
        iteration: int,
        max_iterations: int,
    ) -> GraderResult:
        """
        Grade the current performance against task criteria.
        Returns normalized score between 0.0 and 1.0.
        """
        if task is None:
            return GraderResult(score=0.0, passed=False, feedback="No active task")

        metrics = {}
        breakdown = []
        total_weight = 0.0
        weighted_score = 0.0

        for criterion in task.grading_criteria:
            metric = criterion.metric
            target = criterion.target
            threshold = criterion.threshold
            weight = criterion.weight
            total_weight += weight

            if metric == "execution_time":
                value = current_ms
                if target > threshold:
                    score = (
                        max(0.0, min(1.0, (threshold - value) / (threshold - target) + 1))
                        if value < threshold
                        else 0.0
                    )
                else:
                    score = (
                        max(0.0, min(1.0, 1.0 - (value - target) / (threshold - target)))
                        if value > target
                        else 1.0
                    )
                metrics["execution_time_ms"] = value

            elif metric == "delta_percent":
                delta = ((current_ms - baseline_ms) / baseline_ms * 100) if baseline_ms > 0 else 0
                value = -delta
                score = max(0.0, min(1.0, value / abs(target))) if target > 0 else 0.0
                metrics["delta_percent"] = delta

            elif metric == "memory_usage":
                value = current_memory
                if baseline_memory > 0:
                    reduction = (baseline_memory - value) / baseline_memory * 100
                    score = max(0.0, min(1.0, reduction / 50.0))
                else:
                    score = (
                        1.0
                        if value < threshold
                        else max(0.0, 1.0 - (value - target) / (threshold - target))
                    )
                metrics["memory_usage_mb"] = value

            elif metric == "hotspot_reduction":
                top_hotspot_pct = hotspots[0].percentage if hotspots else 0.0
                value = top_hotspot_pct
                score = max(0.0, min(1.0, 1.0 - value / 50.0))
                metrics["hotspot_percentage"] = value

            else:
                score = 0.5
                value = 0.0

            breakdown.append(
                {
                    "metric": metric,
                    "value": round(value, 2),
                    "target": target,
                    "threshold": threshold,
                    "score": round(score, 3),
                    "weight": weight,
                }
            )
            weighted_score += score * weight

        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        final_score = max(0.0, min(1.0, final_score))

        passed = final_score >= 0.7

        iteration_bonus = 0.0
        if passed:
            remaining = max_iterations - iteration
            iteration_bonus = remaining * 0.02
            final_score = min(1.0, final_score + iteration_bonus)

        feedback = PerformanceGrader._generate_feedback(task, breakdown, final_score, passed)

        return GraderResult(
            score=round(final_score, 3),
            passed=passed,
            metrics=metrics,
            feedback=feedback,
            breakdown=breakdown,
        )

    @staticmethod
    def _generate_feedback(task: Task, breakdown: List[Dict], score: float, passed: bool) -> str:
        """Generate human-readable feedback."""
        if passed:
            return f"Task '{task.name}' completed successfully! Score: {score:.2f}"

        failed_metrics = [b for b in breakdown if b["score"] < 0.5]
        if failed_metrics:
            metric_names = [b["metric"] for b in failed_metrics]
            return f"Task incomplete. Need improvement on: {', '.join(metric_names)}. Current score: {score:.2f}"

        return f"Task in progress. Current score: {score:.2f}"


app = FastAPI(
    title="Code Profiler Environment",
    description="OpenEnv environment for iterative code profiling and performance optimization",
)

state = ProfileState(episode_id=str(uuid.uuid4()))
previous_time_ms = 0.0
previous_memory_mb = 0.0


def reset_env(task_id: Optional[str] = None, language: str = "python") -> ResetResponse:
    """Reset the environment for a specific task or random task."""
    global state, previous_time_ms, previous_memory_mb

    if task_id and task_id in TASK_MAP:
        task = TASK_MAP[task_id]
    else:
        task = AVAILABLE_TASKS[0]

    language = task.target_language if task.target_language != "any" else language

    baseline_times = {
        "string_concatenation": 125.0,
        "linear_search": 85.0,
        "memory_optimization": 150.0,
    }
    baseline_time = baseline_times.get(task.task_type.value, 100.0)
    baseline_memory = 45.0

    state = ProfileState(
        episode_id=str(uuid.uuid4()),
        step_count=0,
        language=language,
        current_task=task,
        current_iteration=0,
        baseline_performance_ms=baseline_time,
        best_performance_ms=baseline_time,
        baseline_memory_mb=baseline_memory,
        best_memory_mb=baseline_memory,
        iteration_results=[],
        is_complete=False,
        final_score=0.0,
    )
    previous_time_ms = baseline_time
    previous_memory_mb = baseline_memory

    observation = ProfileObservation(
        build_status=True,
        build_output=f"Environment ready for task: {task.name}",
        profiler_output=None,
        hotspots=[],
        execution_time_ms=0.0,
        memory_usage_mb=0.0,
        reward=0.0,
        cumulative_score=0.0,
        delta_percent=0.0,
        done=False,
        current_iteration=0,
        max_iterations=task.max_iterations,
        language=language,
        task=task,
        message=f"Task: {task.name}. Difficulty: {task.difficulty.value}. Optimize performance!",
    )

    return ResetResponse(observation=observation, state=state, available_tasks=AVAILABLE_TASKS)


def step_env(action: ProfileAction) -> StepResult:
    """Process a step in the environment."""
    global state, previous_time_ms, previous_memory_mb

    state.step_count += 1
    observation = ProfileObservation(
        build_status=False,
        message="Unknown action",
        current_iteration=state.current_iteration,
        max_iterations=state.current_task.max_iterations if state.current_task else 5,
        language=action.language,
        task=state.current_task,
    )

    grader_result = None
    done = False
    reward = 0.0
    cumulative_score = 0.0

    if action.action_type == "build":
        state.current_iteration += 1
        logger.info(f"[BUILD] Iteration {state.current_iteration} - Language: {action.language}")
        logger.info(f"[BUILD] Task: {state.current_task.name if state.current_task else 'None'}")
        logger.info(f"[BUILD] Target functions for profiling:")

        code_examples = {
            "python": """
# Python e-commerce API - Performance Issues:
# File: server/python/src/app.py

# Issue 1: String concatenation in loop (build_catalog_response)
result = ""
for item in catalog:
    result = result + item['name'] + ","  # SLOW - creates new string each iteration

# Better: result = ','.join([item['name'] for item in catalog])

# Issue 2: Linear search (find_product_linear)
def find_product_linear(products, product_id):
    for p in products:  # O(n) - scans entire list
        if p['id'] == product_id:
            return p
    return None

# Better: Use dict for O(1) lookup: products_map.get(product_id)
""",
            "java": """
// Java e-commerce API - Performance Issues:
// File: server/java/src/main/java/com/example/EcommerceApi.java

// Issue 1: String concatenation in loop
String result = "";
for (Item item : catalog) {
    result = result + item.getName() + ",";  // SLOW - creates StringBuilder each time
}

// Better: StringBuilder or String.join()

// Issue 2: Linear search
public Product findProductLinear(List<Product> products, String id) {
    for (Product p : products) {  // O(n) complexity
        if (p.getId().equals(id)) return p;
    }
    return null;
}

// Better: Use Map<String, Product> for O(1) lookup
""",
            "cpp": """
// C++ e-commerce API - Performance Issues:
// File: server/cpp/src/main.cpp

// Issue 1: Excessive string copies
std::string build_catalog_response(const std::vector<Item>& catalog) {
    std::string result;
    for (const auto& item : catalog) {
        result += item.name;  // Copies string each time
        result += ",";
    }
    return result;
}

// Better: Use std::stringstream or reserve()

// Issue 2: Linear search in vector
Product* find_product_linear(const std::vector<Product>& products, const std::string& id) {
    for (const auto& p : products) {  // O(n) complexity
        if (p.id == id) return &p;
    }
    return nullptr;
}

// Better: Use std::unordered_map<std::string, Product> for O(1)
""",
        }

        logger.info(code_examples.get(action.language, "Unknown language"))
        logger.info(f"[BUILD] Baseline execution time: {previous_time_ms:.2f}ms")

        observation = ProfileObservation(
            build_status=True,
            build_output="Build successful",
            profiler_output=None,
            hotspots=[],
            execution_time_ms=previous_time_ms,
            memory_usage_mb=previous_memory_mb,
            reward=0.0,
            cumulative_score=cumulative_score,
            delta_percent=0.0,
            done=False,
            current_iteration=state.current_iteration,
            max_iterations=state.current_task.max_iterations if state.current_task else 5,
            language=action.language,
            task=state.current_task,
            message=f"Build successful. Iteration {state.current_iteration}/{state.current_task.max_iterations if state.current_task else 5}. Run 'profile' to measure performance.",
        )

    elif action.action_type == "profile":
        if state.current_task is None:
            observation.error = "No active task"
            return StepResult(observation=observation, state=state, grader_result=grader_result)

        state.current_iteration += 1

        performance_multipliers = {
            TaskType.STRING_CONCATENATION: [1.0, 0.65, 0.45, 0.35, 0.30],
            TaskType.LINEAR_SEARCH: [1.0, 0.70, 0.50, 0.40, 0.35],
            TaskType.MEMORY_OPTIMIZATION: [1.0, 0.75, 0.55, 0.45, 0.35, 0.30],
        }

        multipliers = performance_multipliers.get(state.current_task.task_type, [1.0] * 6)
        idx = min(state.current_iteration, len(multipliers) - 1)
        multiplier = multipliers[idx]

        execution_time_ms = state.baseline_performance_ms * multiplier
        memory_mb = state.baseline_memory_mb * (0.9 + 0.1 * multiplier)

        if execution_time_ms < state.best_performance_ms:
            state.best_performance_ms = execution_time_ms
        if memory_mb < state.best_memory_mb:
            state.best_memory_mb = memory_mb

        hotspots = [
            Hotspot(
                function_name="build_catalog_response",
                file_path=f"server/{action.language}/src/app.py",
                line_number=45,
                percentage=35.0 * multiplier,
                self_time_ms=20.0 * multiplier,
                total_time_ms=35.0 * multiplier,
                call_count=150,
            ),
            Hotspot(
                function_name="find_product_linear",
                file_path=f"server/{action.language}/src/app.py",
                line_number=78,
                percentage=22.0 * multiplier,
                self_time_ms=12.0 * multiplier,
                total_time_ms=22.0 * multiplier,
                call_count=85,
            ),
            Hotspot(
                function_name="calculate_order_total",
                file_path=f"server/{action.language}/src/app.py",
                line_number=112,
                percentage=18.0 * multiplier,
                self_time_ms=10.0 * multiplier,
                total_time_ms=18.0 * multiplier,
                call_count=200,
            ),
        ]

        logger.info(f"[PROFILE] ============================================")
        logger.info(f"[PROFILE] Iteration {state.current_iteration} Profile Results")
        logger.info(f"[PROFILE] Language: {action.language}")
        logger.info(f"[PROFILE] Task: {state.current_task.name if state.current_task else 'None'}")
        logger.info(f"[PROFILE] ============================================")
        logger.info(
            f"[PROFILE] Execution Time: {execution_time_ms:.2f}ms (baseline: {state.baseline_performance_ms:.2f}ms)"
        )
        logger.info(f"[PROFILE] Memory Usage: {memory_mb:.2f}MB")
        logger.info(f"[PROFILE] Delta: {delta_percent:+.2f}%")
        logger.info(f"[PROFILE] ============================================")
        logger.info(f"[PROFILE] TOP HOTSPOTS (identified by profiler):")
        logger.info(f"[PROFILE] ============================================")

        for i, h in enumerate(hotspots, 1):
            logger.info(f"[PROFILE] {i}. {h.function_name}")
            logger.info(f"[PROFILE]    File: {h.file_path}:{h.line_number}")
            logger.info(
                f"[PROFILE]    Time: {h.self_time_ms:.2f}ms (self), {h.total_time_ms:.2f}ms (total)"
            )
            logger.info(f"[PROFILE]    Impact: {h.percentage:.1f}% of total execution time")
            logger.info(f"[PROFILE]    Calls: {h.call_count}")

            fix_suggestions = {
                "build_catalog_response": "Use string.join() or StringBuilder instead of + concatenation",
                "find_product_linear": "Use dict/hash map for O(1) lookup instead of O(n) loop",
                "calculate_order_total": "Cache intermediate results, avoid repeated calculations",
            }
            if h.function_name in fix_suggestions:
                logger.info(f"[PROFILE]    Fix: {fix_suggestions[h.function_name]}")
            logger.info(f"[PROFILE] ------------------------------------------------")

        logger.info(f"[PROFILE] Score: {grader_result.score:.2f}")
        logger.info(f"[PROFILE] Status: {'PASS' if grader_result.passed else 'IN PROGRESS'}")
        logger.info(f"[PROFILE] ============================================")

        grader_result = PerformanceGrader.grade_task(
            task=state.current_task,
            baseline_ms=state.baseline_performance_ms,
            current_ms=execution_time_ms,
            baseline_memory=state.baseline_memory_mb,
            current_memory=memory_mb,
            hotspots=hotspots,
            iteration=state.current_iteration,
            max_iterations=state.current_task.max_iterations,
        )

        delta_percent = (
            (
                (execution_time_ms - state.baseline_performance_ms)
                / state.baseline_performance_ms
                * 100
            )
            if state.baseline_performance_ms > 0
            else 0
        )

        reward = grader_result.score
        cumulative_score = grader_result.score

        iteration_result = IterationResult(
            iteration=state.current_iteration,
            language=action.language,
            build_success=True,
            profiler_output="Profile complete",
            hotspots=hotspots,
            execution_time_ms=execution_time_ms,
            memory_usage_mb=memory_mb,
            reward=reward,
            cumulative_score=cumulative_score,
            delta_percent=delta_percent,
            fix_applied=action.code_fix,
        )
        state.iteration_results.append(iteration_result)

        done = state.current_iteration >= state.current_task.max_iterations

        if done:
            state.is_complete = True
            state.final_score = grader_result.score

        observation = ProfileObservation(
            build_status=True,
            build_output="Build successful",
            profiler_output="Profile complete",
            hotspots=hotspots,
            execution_time_ms=execution_time_ms,
            memory_usage_mb=memory_mb,
            reward=reward,
            cumulative_score=cumulative_score,
            delta_percent=delta_percent,
            done=done,
            current_iteration=state.current_iteration,
            max_iterations=state.current_task.max_iterations,
            language=action.language,
            task=state.current_task,
            message=grader_result.feedback,
        )

        previous_time_ms = execution_time_ms
        previous_memory_mb = memory_mb

    elif action.action_type == "fix":
        logger.info(f"[FIX] ============================================")
        logger.info(f"[FIX] Applying code fix - Iteration {state.current_iteration}")
        logger.info(f"[FIX] Language: {action.language}")
        logger.info(f"[FIX] Task: {state.current_task.name if state.current_task else 'None'}")
        logger.info(
            f"[FIX] Fix description: {action.code_fix[:200] if action.code_fix else 'No description'}"
        )
        logger.info(f"[FIX] Note: Run 'profile' action to measure improvement")
        logger.info(f"[FIX] ============================================")
        observation = ProfileObservation(
            build_status=True,
            build_output="Fix applied",
            profiler_output=None,
            hotspots=[],
            execution_time_ms=previous_time_ms,
            memory_usage_mb=previous_memory_mb,
            reward=0.0,
            cumulative_score=cumulative_score,
            delta_percent=0.0,
            done=False,
            current_iteration=state.current_iteration,
            max_iterations=state.current_task.max_iterations if state.current_task else 5,
            language=action.language,
            task=state.current_task,
            message=f"Fix applied. Run 'profile' to measure improvement.",
        )

    elif action.action_type == "submit":
        done = True
        state.is_complete = True

        logger.info(f"[SUBMIT] ============================================")
        logger.info(f"[SUBMIT] Task Submission")
        logger.info(f"[SUBMIT] Task: {state.current_task.name if state.current_task else 'None'}")
        logger.info(f"[SUBMIT] Language: {action.language}")
        logger.info(f"[SUBMIT] Total iterations: {state.current_iteration}")
        logger.info(f"[SUBMIT] Best execution time: {state.best_performance_ms:.2f}ms")
        logger.info(f"[SUBMIT] Baseline: {state.baseline_performance_ms:.2f}ms")

        if grader_result is None and state.current_task:
            grader_result = PerformanceGrader.grade_task(
                task=state.current_task,
                baseline_ms=state.baseline_performance_ms,
                current_ms=previous_time_ms,
                baseline_memory=state.baseline_memory_mb,
                current_memory=previous_memory_mb,
                hotspots=[],
                iteration=state.current_iteration,
                max_iterations=state.current_task.max_iterations,
            )

        if grader_result:
            state.final_score = grader_result.score
            cumulative_score = grader_result.score
            reward = grader_result.score

        improvement = (
            (
                (state.baseline_performance_ms - state.best_performance_ms)
                / state.baseline_performance_ms
                * 100
            )
            if state.baseline_performance_ms > 0
            else 0
        )

        logger.info(f"[SUBMIT] Improvement: {improvement:.1f}%")
        logger.info(f"[SUBMIT] Final Score: {state.final_score:.2f}")
        logger.info(f"[SUBMIT] Status: {'PASS' if state.final_score >= 0.7 else 'FAIL'}")
        logger.info(f"[SUBMIT] ============================================")

        observation = ProfileObservation(
            build_status=True,
            build_output="Task submitted",
            profiler_output=None,
            hotspots=[],
            execution_time_ms=previous_time_ms,
            memory_usage_mb=previous_memory_mb,
            reward=reward,
            cumulative_score=cumulative_score,
            delta_percent=0.0,
            done=True,
            current_iteration=state.current_iteration,
            max_iterations=state.current_task.max_iterations if state.current_task else 5,
            language=action.language,
            task=state.current_task,
            message=f"Task complete. Final Score: {state.final_score:.2f} (Improvement: {improvement:.1f}%)",
        )

    return StepResult(observation=observation, state=state, grader_result=grader_result)


@app.get("/")
async def root():
    from fastapi.responses import JSONResponse

    return JSONResponse(
        content={
            "message": "Code Profiler Environment API",
            "status": "running",
            "version": "1.0.0-hackathon",
            "tasks": [t.task_id for t in AVAILABLE_TASKS],
        },
        media_type="application/json",
    )


@app.get("/health")
async def health():
    from fastapi.responses import JSONResponse

    return JSONResponse(content={"status": "healthy"}, media_type="application/json")


@app.post("/reset", response_model=ResetResponse)
async def reset(data: dict = None):
    task_id = None
    language = "python"
    if data:
        task_id = data.get("task_id")
        language = data.get("language", "python")
    return reset_env(task_id=task_id, language=language)


@app.post("/step", response_model=StepResult)
async def step(action: ProfileAction):
    return step_env(action)


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


@app.get("/tasks")
async def get_tasks():
    return [t.model_dump() for t in AVAILABLE_TASKS]


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id in TASK_MAP:
        return TASK_MAP[task_id].model_dump()
    return {"error": "Task not found"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            action_type = data.get("type")

            if action_type == "reset":
                response = reset_env(
                    task_id=data.get("task_id"), language=data.get("language", "python")
                )
                await websocket.send_json(
                    {
                        "type": "reset_response",
                        "observation": response.observation.model_dump(),
                        "state": response.state.model_dump(),
                        "available_tasks": [t.model_dump() for t in response.available_tasks],
                    }
                )

            elif action_type == "step":
                action = ProfileAction(**data.get("action", {}))
                result = step_env(action)
                response_data = {
                    "type": "step_response",
                    "observation": result.observation.model_dump(),
                    "state": result.state.model_dump(),
                }
                if result.grader_result:
                    response_data["grader_result"] = result.grader_result.model_dump()
                await websocket.send_json(response_data)

            elif action_type == "state":
                await websocket.send_json({"type": "state", "data": state.model_dump()})

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
