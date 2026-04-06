"""Code Profiler Environment server implementation."""

import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from openenv import Environment
from openenv.core.rubrics import Rubric

from ..models import (
    Hotspot,
    IterationResult,
    ProfileAction,
    ProfileObservation,
    ProfileState,
    StepResult,
)
from src.reward_calculator import PerformanceRewardCalculator
from src.hotspot_analyzer import HotspotAnalyzer
from src.profiler_runner import get_profiler_runner


class CodeProfilerRubric(Rubric):
    """Rubric for computing performance rewards."""

    def __init__(self):
        super().__init__()
        self.calculators: Dict[str, PerformanceRewardCalculator] = {
            "python": PerformanceRewardCalculator(100.0),
            "java": PerformanceRewardCalculator(100.0),
            "cpp": PerformanceRewardCalculator(100.0),
        }

    def forward(self, action: ProfileAction, observation: ProfileObservation) -> float:
        """Compute reward based on action and observation."""
        return observation.reward

    def get_calculator(self, language: str) -> PerformanceRewardCalculator:
        return self.calculators.get(language, PerformanceRewardCalculator(100.0))

    def reset(self, language: str, baseline_ms: float):
        self.calculators[language] = PerformanceRewardCalculator(baseline_ms)


class CodeProfilerEnvironment(Environment):
    """
    OpenEnv environment for code profiling and performance optimization.

    This environment wraps code profiling tools (Austin for Python/C++,
    async-profiler for Java) and provides a Gymnasium-style interface
    for iterative performance optimization.

    The agent can:
    1. Build code in a target language
    2. Profile the code to identify hotspots
    3. Apply fixes to address hotspots
    4. Measure improvement/degradation

    Rewards are computed as graded percentage improvement/degradation.
    """

    def __init__(self):
        super().__init__()
        self.rubric = CodeProfilerRubric()

        self._state = ProfileState()
        self._languages = ["python", "java", "cpp"]
        self._hotspot_analyzer = HotspotAnalyzer()

        self._base_path = Path(__file__).parent.parent.parent
        self._code_paths: Dict[str, Path] = {
            "python": self._base_path / "server" / "python" / "src",
            "java": self._base_path / "server" / "java" / "src",
            "cpp": self._base_path / "server" / "cpp" / "src",
        }

        self._current_output: Optional[str] = None
        self._current_hotspots: List[Hotspot] = []
        self._previous_time_ms: float = 0.0

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        language: str = "python",
        **kwargs,
    ) -> ProfileObservation:
        """Reset the environment to initial state."""
        self._state = ProfileState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            language=language,
            current_iteration=0,
            baseline_performance_ms=0.0,
            iteration_results=[],
            is_complete=False,
        )

        for lang in self._languages:
            self.rubric.reset(lang, 100.0)

        self._previous_time_ms = 0.0

        return ProfileObservation(
            build_status=True,
            build_output="Environment ready. Provide initial code to profile.",
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

    def step(self, action: ProfileAction) -> ProfileObservation:
        """Execute a single step."""
        self._state.step_count += 1

        if action.language not in self._languages:
            return self._make_error_observation(f"Unsupported language: {action.language}", action)

        if action.iteration != self._state.current_iteration:
            return self._make_error_observation(
                f"Iteration mismatch. Expected {self._state.current_iteration}, got {action.iteration}",
                action,
            )

        if action.iteration >= 5:
            self._state.is_complete = True
            return ProfileObservation(
                build_status=True,
                build_output="Maximum iterations reached.",
                profiler_output=None,
                hotspots=[],
                execution_time_ms=self._state.best_performance_ms,
                reward=0.0,
                delta_percent=0.0,
                done=True,
                current_iteration=self._state.current_iteration,
                language=action.language,
                message=f"Episode complete. Best performance: {self._state.best_performance_ms:.2f}ms",
            )

        if action.action_type == "build":
            return self._handle_build(action)
        elif action.action_type == "profile":
            return self._handle_profile(action)
        elif action.action_type == "fix":
            return self._handle_fix(action)
        elif action.action_type == "test":
            return self._handle_test(action)
        else:
            return self._make_error_observation(
                f"Unknown action type: {action.action_type}", action
            )

    def _handle_build(self, action: ProfileAction) -> ProfileObservation:
        """Handle build action."""
        build_success, build_output = self._build_code(action.language)

        if build_success:
            self._state.current_iteration += 1
            self._state.language = action.language

            return ProfileObservation(
                build_status=True,
                build_output=build_output,
                profiler_output=None,
                hotspots=[],
                execution_time_ms=0.0,
                reward=0.0,
                delta_percent=0.0,
                done=False,
                current_iteration=self._state.current_iteration,
                language=action.language,
                message=f"Build successful. Ready to profile iteration {self._state.current_iteration}.",
            )
        else:
            return ProfileObservation(
                build_status=False,
                build_output=build_output,
                profiler_output=None,
                hotspots=[],
                execution_time_ms=0.0,
                reward=-1.0,
                delta_percent=0.0,
                done=False,
                current_iteration=self._state.current_iteration,
                language=action.language,
                message=f"Build failed: {build_output}",
            )

    def _handle_profile(self, action: ProfileAction) -> ProfileObservation:
        """Handle profile action."""
        execution_time_ms, profiler_output, hotspots = self._profile_code(
            action.language, action.test_input
        )

        reward, delta_percent = self.rubric.get_calculator(action.language).compute_reward(
            execution_time_ms, self._previous_time_ms
        )

        if self._state.current_iteration == 1 and self._state.baseline_performance_ms == 0:
            self._state.baseline_performance_ms = execution_time_ms
            self._state.best_performance_ms = execution_time_ms
            reward = 0.0
            delta_percent = 0.0

        if execution_time_ms < self._state.best_performance_ms:
            self._state.best_performance_ms = execution_time_ms

        self._previous_time_ms = execution_time_ms

        self._state.iteration_results.append(
            IterationResult(
                iteration=self._state.current_iteration,
                language=action.language,
                build_success=True,
                profiler_output=profiler_output,
                hotspots=hotspots,
                execution_time_ms=execution_time_ms,
                reward=reward,
                delta_percent=delta_percent,
                timestamp=time.time(),
            )
        )

        top_hotspot = hotspots[0] if hotspots else None
        message = f"Profile complete. Execution: {execution_time_ms:.2f}ms. "
        if top_hotspot:
            message += f"Top hotspot: {top_hotspot.function_name} ({top_hotspot.percentage:.1f}%)"

        return ProfileObservation(
            build_status=True,
            build_output="Build successful",
            profiler_output=profiler_output,
            hotspots=hotspots,
            execution_time_ms=execution_time_ms,
            reward=reward,
            delta_percent=delta_percent,
            done=False,
            current_iteration=self._state.current_iteration,
            language=action.language,
            message=message,
        )

    def _handle_fix(self, action: ProfileAction) -> ProfileObservation:
        """Handle code fix action."""
        if not action.code_fix:
            return self._make_error_observation("No code fix provided", action)

        fix_success = self._apply_fix(action.language, action.code_fix)

        if fix_success:
            self._state.current_iteration += 1

            return ProfileObservation(
                build_status=True,
                build_output=f"Fix applied: {action.code_fix[:100]}",
                profiler_output=None,
                hotspots=self._state.iteration_results[-1].hotspots
                if self._state.iteration_results
                else [],
                execution_time_ms=self._previous_time_ms,
                reward=0.0,
                delta_percent=0.0,
                done=False,
                current_iteration=self._state.current_iteration,
                language=action.language,
                message=f"Fix applied. Ready to profile iteration {self._state.current_iteration}.",
            )
        else:
            return ProfileObservation(
                build_status=False,
                build_output="Failed to apply fix",
                profiler_output=None,
                hotspots=[],
                execution_time_ms=self._previous_time_ms,
                reward=-1.0,
                delta_percent=0.0,
                done=False,
                current_iteration=self._state.current_iteration,
                language=action.language,
                message="Failed to apply code fix.",
            )

    def _handle_test(self, action: ProfileAction) -> ProfileObservation:
        """Handle test action - run smoke test."""
        test_success, test_output = self._run_smoke_test(action.language)

        return ProfileObservation(
            build_status=test_success,
            build_output=test_output,
            profiler_output=None,
            hotspots=self._state.iteration_results[-1].hotspots
            if self._state.iteration_results
            else [],
            execution_time_ms=self._previous_time_ms,
            reward=0.0,
            delta_percent=0.0,
            done=False,
            current_iteration=self._state.current_iteration,
            language=action.language,
            message=f"Smoke test {'passed' if test_success else 'failed'}.",
        )

    def _build_code(self, language: str) -> tuple[bool, str]:
        """Build code in specified language."""
        code_path = self._code_paths.get(language)
        if not code_path:
            return False, f"No code path for {language}"

        try:
            if language == "python":
                result = subprocess.run(
                    ["python", "-m", "py_compile"] + list(code_path.glob("*.py")),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            elif language == "java":
                result = subprocess.run(
                    ["javac"] + list(code_path.glob("**/*.java")),
                    capture_output=True,
                    text=True,
                    cwd=code_path,
                    timeout=60,
                )
            elif language == "cpp":
                build_dir = code_path.parent / "build"
                build_dir.mkdir(exist_ok=True)
                result = subprocess.run(
                    ["cmake", "-B", str(build_dir), str(code_path.parent)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    result = subprocess.run(
                        ["cmake", "--build", str(build_dir)],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

            return result.returncode == 0, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "Build timed out"
        except FileNotFoundError as e:
            return False, f"Build tool not found: {e}"
        except Exception as e:
            return False, str(e)

    def _profile_code(
        self, language: str, test_input: Optional[str] = None
    ) -> tuple[float, str, List[Hotspot]]:
        """Profile code in specified language."""
        code_path = self._code_paths.get(language)
        if not code_path:
            return 0.0, f"No code path for {language}", []

        try:
            profiler = get_profiler_runner(language)
            execution_time = 0.0
            output = ""
            hotspots: List[Hotspot] = []

            if language == "python":
                main_script = code_path / "app.py"
                if main_script.exists():
                    result = profiler.profile(str(main_script), duration_seconds=5)
                    if result.success:
                        execution_time = self._measure_execution_time_python(code_path)
                        parsed = profiler.parse_output(result.output)
                        hotspots = self._convert_to_hotspots(parsed)

            elif language == "java":
                jar_path = code_path.parent / "target" / "app.jar"
                if jar_path.exists():
                    result = profiler.profile(str(jar_path), duration_seconds=5)
                    if result.success:
                        execution_time = self._measure_execution_time_java(jar_path)
                        parsed = profiler.parse_output(result.output)
                        hotspots = self._convert_to_hotspots(parsed)

            elif language == "cpp":
                binary_path = code_path.parent / "build" / "ecommerce_api"
                if binary_path.exists():
                    result = profiler.profile(str(binary_path), duration_seconds=5)
                    if result.success:
                        execution_time = self._measure_execution_time_cpp(binary_path)
                        parsed = profiler.parse_output(result.output)
                        hotspots = self._convert_to_hotspots(parsed)

            return execution_time, output, hotspots

        except Exception as e:
            return 100.0, str(e), []

    def _measure_execution_time_python(self, code_path: Path) -> float:
        """Measure Python execution time."""
        try:
            result = subprocess.run(
                [
                    "python",
                    "-c",
                    "import time; start=time.time(); "
                    f"exec(open('{code_path}/app.py').read()); "
                    "print(f'{time.time()-start:.6f}')",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return float(result.stdout.strip()) * 1000
        except Exception:
            pass
        return 100.0

    def _measure_execution_time_java(self, jar_path: Path) -> float:
        """Measure Java execution time."""
        try:
            start = time.time()
            subprocess.run(["java", "-jar", str(jar_path)], capture_output=True, timeout=10)
            return (time.time() - start) * 1000
        except Exception:
            pass
        return 100.0

    def _measure_execution_time_cpp(self, binary_path: Path) -> float:
        """Measure C++ execution time."""
        try:
            start = time.time()
            subprocess.run([str(binary_path)], capture_output=True, timeout=10)
            return (time.time() - start) * 1000
        except Exception:
            pass
        return 100.0

    def _apply_fix(self, language: str, fix_code: str) -> bool:
        """Apply code fix to source file."""
        code_path = self._code_paths.get(language)
        if not code_path:
            return False

        try:
            if language == "python":
                app_file = code_path / "app.py"
            elif language == "java":
                app_file = code_path / "com" / "ecommerce" / "api" / "ECommerceAPI.java"
            elif language == "cpp":
                app_file = code_path / "main.cpp"
            else:
                return False

            with open(app_file, "w") as f:
                f.write(fix_code)

            return True
        except Exception:
            return False

    def _run_smoke_test(self, language: str) -> tuple[bool, str]:
        """Run smoke test on the code."""
        code_path = self._code_paths.get(language)
        if not code_path:
            return False, f"No code path for {language}"

        try:
            if language == "python":
                result = subprocess.run(
                    [
                        "python",
                        "-c",
                        f"import sys; sys.path.insert(0, '{code_path}'); "
                        "exec(open('{code_path}/app.py').read())",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            else:
                result = subprocess.run(
                    ["echo", "Smoke test placeholder"], capture_output=True, text=True
                )

            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def _convert_to_hotspots(self, parsed: list) -> List[Hotspot]:
        """Convert parsed profiler output to Hotspot objects."""
        hotspots = []
        for item in parsed[:5]:
            if isinstance(item, dict):
                hotspots.append(
                    Hotspot(
                        function_name=item.get("function", "unknown"),
                        file_path=item.get("file"),
                        line_number=item.get("line"),
                        self_time_ms=item.get("self_time", item.get("samples", 0)),
                        total_time_ms=item.get("total_time", item.get("samples", 0)),
                        call_count=item.get("call_count", 1),
                        percentage=item.get("percentage", 0.0),
                    )
                )
        return hotspots

    def _make_error_observation(self, message: str, action: ProfileAction) -> ProfileObservation:
        """Create error observation."""
        return ProfileObservation(
            build_status=False,
            build_output=message,
            profiler_output=None,
            hotspots=[],
            execution_time_ms=self._previous_time_ms,
            reward=-1.0,
            delta_percent=0.0,
            done=False,
            current_iteration=self._state.current_iteration,
            language=action.language,
            message=f"Error: {message}",
        )

    def state(self) -> ProfileState:
        """Get current environment state."""
        return self._state
