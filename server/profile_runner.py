"""
Unified Profile Runner for Code Profiler Environment (v2).
Provides profiling capabilities for Python, Java, and C++ code using:
- austin: Frame sampler for Python and C++
- async-profiler: CPU/memory profiler for Java
"""

import subprocess
import time
import tempfile
import os
import logging
import signal
import threading
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

JAVA_MAIN_CLASS = "com.ecommerce.api.ECommerceAPI"
JAVA_SRC_PATH = "/app/server/java/src"
JAVA_CLASSPATH = "/app/server/java/src:/app/java_classes"
CPP_SRC_PATH = "/app/server/cpp/src"
CPP_BINARY = "/app/server/cpp/build/ecommerce_api"
ASYNC_PROFILER_HOME = "/tmp/async-profiler"
PYTHON_SRC_PATH = "/app/server/python/src"
PYTHON_APP_PATH = "/app/server/python/src/app.py"

PYTHON_API_PORT = 5000
JAVA_API_PORT = 5001
CPP_API_PORT = 5002


@dataclass
class Hotspot:
    """Represents a performance hotspot."""

    function_name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    self_time_ms: float = 0.0
    total_time_ms: float = 0.0
    call_count: int = 0
    percentage: float = 0.0


@dataclass
class ProfileResult:
    """Result from profiling."""

    success: bool
    execution_time_ms: float
    hotspots: List[Hotspot]
    output: str = ""
    error: Optional[str] = None


def measure_console_execution_time(
    cmd: List[str], warmup_runs: int = 1, measure_runs: int = 3
) -> float:
    """
    Measure actual execution time for a console application.

    Args:
        cmd: Command to run as list of strings
        warmup_runs: Number of warmup runs before measuring
        measure_runs: Number of runs to average

    Returns:
        Average execution time in milliseconds
    """
    execution_times = []

    # Warmup runs
    for _ in range(warmup_runs):
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception:
            pass

    # Measure runs
    for _ in range(measure_runs):
        try:
            start = time.time()
            subprocess.run(cmd, capture_output=True, timeout=10)
            elapsed = (time.time() - start) * 1000  # Convert to ms
            execution_times.append(elapsed)
        except Exception:
            pass

    return sum(execution_times) / len(execution_times) if execution_times else 0.0


class PythonProfiler:
    """Profiler for Python code using austin frame sampler."""

    @staticmethod
    def profile_with_austin(
        script_path: str = None, duration: int = 5
    ) -> ProfileResult:
        """
        Profile Python script using austin frame sampler.

        Austin is a frame sampler that captures stack traces at regular intervals.
        It works by using kernel probes to sample the running process.

        Usage: austin -x <duration> -o <output.mojo> python <script.py>
        """
        if script_path is None:
            script_path = os.path.join(PYTHON_SRC_PATH, "app.py")

        if not os.path.exists(script_path):
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=f"Python script not found: {script_path}",
            )

        with tempfile.NamedTemporaryFile(suffix=".mojo", delete=False) as f:
            output_file = f.name

        try:
            # First measure actual execution time by making requests
            avg_time = PythonProfiler.profile_request(
                duration=min(duration, 3)
            ).execution_time_ms

            result = subprocess.run(
                [
                    "austin",
                    "-x",
                    str(duration),
                    "-o",
                    output_file,
                    "python",
                    script_path,
                ],
                capture_output=True,
                timeout=duration + 30,
            )

            execution_time = avg_time if avg_time > 0 else duration * 1000.0

            if result.returncode == 0 and os.path.exists(output_file):
                try:
                    with open(output_file, encoding="utf-8", errors="replace") as f:
                        output = f.read()
                except Exception:
                    output = ""

                hotspots = PythonProfiler._parse_austin_output(output, execution_time)

                return ProfileResult(
                    success=True,
                    execution_time_ms=execution_time,
                    hotspots=hotspots,
                    output=output,
                )
            else:
                try:
                    error_msg = (
                        result.stderr.decode("utf-8", errors="replace")
                        if result.stderr
                        else "austin failed"
                    )
                except Exception:
                    error_msg = "austin failed with encoding error"
                logger.warning(f"austin failed: {error_msg}, falling back to simulated")
                return PythonProfiler._fallback_profile(execution_time)

        except FileNotFoundError:
            logger.warning("austin not found, measuring actual execution time")
            # Measure actual execution time via HTTP requests
            measured_result = PythonProfiler.profile_request(duration=min(duration, 3))
            return PythonProfiler._fallback_profile(
                measured_result.execution_time_ms
                if measured_result.execution_time_ms > 0
                else duration * 1000.0
            )
        except subprocess.TimeoutExpired:
            logger.warning("austin timed out, measuring actual execution time")
            measured_result = PythonProfiler.profile_request(duration=min(duration, 3))
            return PythonProfiler._fallback_profile(
                measured_result.execution_time_ms
                if measured_result.execution_time_ms > 0
                else duration * 1000.0
            )
        except Exception as e:
            logger.warning(f"austin error: {e}, measuring actual execution time")
            measured_result = PythonProfiler.profile_request(duration=min(duration, 3))
            return PythonProfiler._fallback_profile(
                measured_result.execution_time_ms
                if measured_result.execution_time_ms > 0
                else duration * 1000.0
            )
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @staticmethod
    def _parse_austin_output(output: str, total_time_ms: float) -> List[Hotspot]:
        """Parse austin collapsed stack format: frame1;frame2;frameN;[metric]"""
        hotspots = []
        seen_funcs = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Austin collapsed format: frame1;frame2;...;[metric] or frame1;frame2;...;metric
            # Extract metric (time in microseconds, in square brackets at end)
            if "[" in line and "]" in line:
                metric_str = line[line.rfind("[") + 1 : line.rfind("]")]
                try:
                    time_us = float(metric_str)
                except ValueError:
                    time_us = 0.0
                # Remove the metric part to get the stack
                stack_part = line[: line.rfind("[")].rstrip(";")
            else:
                # No metric brackets - skip or try alternative parsing
                parts = line.split(";")
                if len(parts) >= 2:
                    try:
                        time_us = float(parts[-1])
                        stack_part = ";".join(parts[:-1])
                    except ValueError:
                        continue
                else:
                    continue

            if not stack_part:
                continue

            # Split stack by semicolon to get individual frames
            frames = [f.strip() for f in stack_part.split(";") if f.strip()]
            if not frames:
                continue

            # Get the innermost Python function (skip C frames)
            func_name = None
            file_path = "app.py"
            for frame in reversed(frames):
                # Skip known non-Python frames
                if any(
                    skip in frame
                    for skip in ("python", "PyRun", "libc", "main", "start_thread")
                ):
                    continue
                # Parse frame like "module.py:123" or "function"
                if ":" in frame:
                    func_name = frame.split(":")[0]
                    # Extract line number if present
                    try:
                        line_num = int(frame.split(":")[-1])
                    except ValueError:
                        line_num = None
                    file_path = func_name
                    if line_num:
                        file_path = f"{func_name}:{line_num}"
                else:
                    func_name = frame
                break

            if not func_name:
                func_name = frames[-1] if frames else "unknown"

            # Aggregate by function
            if func_name in seen_funcs:
                seen_funcs[func_name].call_count += 1
                seen_funcs[func_name].self_time_ms += time_us / 1000.0
            else:
                seen_funcs[func_name] = Hotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=None,
                    self_time_ms=time_us / 1000.0,
                    total_time_ms=time_us / 1000.0,
                    call_count=1,
                    percentage=0.0,
                )

        hotspots = list(seen_funcs.values())
        if not hotspots:
            return PythonProfiler._generate_hotspots(total_time_ms)

        total_samples = sum(h.call_count for h in hotspots) or 1
        total_time = sum(h.self_time_ms for h in hotspots) or 1
        for h in hotspots:
            h.percentage = (h.self_time_ms / total_time) * 100
            h.total_time_ms = h.self_time_ms * 1.1

        return sorted(hotspots, key=lambda h: h.self_time_ms, reverse=True)[:10]

    @staticmethod
    def _fallback_profile(execution_time_ms: float) -> ProfileResult:
        """Generate simulated hotspot data when real profiling fails."""
        hotspots = PythonProfiler._generate_hotspots(execution_time_ms)
        return ProfileResult(
            success=True,
            execution_time_ms=execution_time_ms,
            hotspots=hotspots,
            output="(simulated - austin not available)",
        )

    @staticmethod
    def profile_request(
        port: int = PYTHON_API_PORT, duration: int = 5
    ) -> ProfileResult:
        """Profile Python Flask API by making requests and measuring time."""
        import httpx

        execution_times = []
        try:
            for _ in range(duration * 2):
                req_start = time.time()
                try:
                    response = httpx.get(
                        f"http://localhost:{port}/catalog", timeout=5.0
                    )
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = (
                sum(execution_times) / len(execution_times) if execution_times else 0.0
            )
            hotspots = PythonProfiler._generate_hotspots(avg_time)

            return ProfileResult(
                success=True,
                execution_time_ms=avg_time,
                hotspots=hotspots,
                output=f"Average execution time: {avg_time:.2f}ms",
            )
        except Exception as e:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=str(e),
            )

    @staticmethod
    def _generate_hotspots(execution_time_ms: float) -> List[Hotspot]:
        """Generate simulated hotspot data based on execution time."""
        hotspots = []
        total_time = execution_time_ms

        hotspot_configs = [
            ("build_catalog_response", "app.py", 45, 0.28),
            ("find_product_by_id_linear", "app.py", 78, 0.18),
            ("calculate_order_total", "app.py", 112, 0.15),
            ("deep_copy_product", "app.py", 134, 0.12),
            ("filter_products_by_category", "app.py", 156, 0.08),
        ]

        for func_name, file_path, line, impact in hotspot_configs:
            self_time = total_time * impact
            hotspots.append(
                Hotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=line,
                    self_time_ms=self_time,
                    total_time_ms=self_time * 1.3,
                    call_count=int(150 * (1 - impact * 0.5)),
                    percentage=impact * 100,
                )
            )

        return hotspots


class JavaProfiler:
    """Profiler for Java code using async-profiler."""

    _java_process = None
    _java_pid = None

    @staticmethod
    def _ensure_java_running() -> Optional[int]:
        """Ensure Java application is running and return PID."""
        if JavaProfiler._java_pid and JavaProfiler._java_process:
            try:
                JavaProfiler._java_process.poll()
                if JavaProfiler._java_process.returncode is None:
                    return JavaProfiler._java_pid
            except Exception:
                pass

        if not os.path.exists(ASYNC_PROFILER_HOME):
            logger.warning("async-profiler not installed")
            return None

        if not os.path.exists(JAVA_SRC_PATH):
            logger.warning(f"Java source path not found: {JAVA_SRC_PATH}")
            return None
        if not os.path.exists("/app/java_classes"):
            logger.warning(f"Java classes path not found: /app/java_classes")
            return None

        try:
            JavaProfiler._java_process = subprocess.Popen(
                ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            JavaProfiler._java_pid = JavaProfiler._java_process.pid
            time.sleep(1)
            return JavaProfiler._java_pid
        except Exception as e:
            logger.error(f"Failed to start Java process: {e}")
            return None

    @staticmethod
    def profile_with_async_profiler(duration: int = 5) -> ProfileResult:
        """
        Profile Java using async-profiler.

        async-profiler attaches to a running JVM process and samples
        CPU stack traces. It requires:
        1. Running Java process with PID
        2. async-profiler installed at ASYNC_PROFILER_HOME

        Usage: profiler.sh -d <duration> -f <output.html> -e cpu <pid>
        """
        pid = JavaProfiler._ensure_java_running()

        if pid is None:
            # Measure actual Java execution time
            avg_time = measure_console_execution_time(
                ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                warmup_runs=1,
                measure_runs=3,
            )
            return JavaProfiler._fallback_profile(avg_time if avg_time > 0 else 5000.0)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    f"{ASYNC_PROFILER_HOME}/bin/asprof",
                    "-d",
                    str(duration),
                    "-f",
                    output_file,
                    "-e",
                    "cpu",
                    str(pid),
                ],
                capture_output=True,
                timeout=duration + 30,
            )

            if result.returncode == 0 and os.path.exists(output_file):
                with open(output_file) as f:
                    output = f.read()

                hotspots = JavaProfiler._parse_async_profiler_output(output)

                return ProfileResult(
                    success=True,
                    execution_time_ms=duration * 1000.0,
                    hotspots=hotspots,
                    output=output[:1000],
                )
            else:
                error_msg = (
                    result.stderr.decode("utf-8", errors="replace")
                    if result.stderr
                    else "async-profiler failed"
                )
                logger.warning(
                    f"async-profiler failed: {error_msg}, measuring actual time"
                )
                avg_time = measure_console_execution_time(
                    ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                    warmup_runs=1,
                    measure_runs=3,
                )
                return JavaProfiler._fallback_profile(
                    avg_time if avg_time > 0 else duration * 1000.0
                )

        except subprocess.TimeoutExpired:
            avg_time = measure_console_execution_time(
                ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                warmup_runs=1,
                measure_runs=3,
            )
            return ProfileResult(
                success=False,
                execution_time_ms=avg_time if avg_time > 0 else duration * 1000.0,
                hotspots=[],
                error="Profile timed out",
            )
        except FileNotFoundError:
            logger.warning(
                "async-profiler not found, measuring actual Java execution time"
            )
            avg_time = measure_console_execution_time(
                ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                warmup_runs=1,
                measure_runs=3,
            )
            return JavaProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )
        except Exception as e:
            logger.warning(f"async-profiler error: {e}, measuring actual time")
            avg_time = measure_console_execution_time(
                ["java", "-cp", JAVA_CLASSPATH, JAVA_MAIN_CLASS],
                warmup_runs=1,
                measure_runs=3,
            )
            return JavaProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @staticmethod
    def _parse_async_profiler_output(output: str) -> List[Hotspot]:
        """Parse async-profiler HTML/text output."""
        hotspots = []

        for line in output.split("\n"):
            line = line.strip()
            if not line or "---" in line:
                continue

            if (
                "buildCatalogResponse" in line
                or "findProductLinear" in line
                or "calculateOrderTotal" in line
            ):
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        func = parts[0].strip()
                        samples = (
                            int(parts[1].strip().replace(",", ""))
                            if parts[1].strip().replace(",", "").isdigit()
                            else 0
                        )
                        pct = (
                            float(parts[-1].strip().replace("%", ""))
                            if "%" in parts[-1]
                            else 5.0
                        )

                        hotspots.append(
                            Hotspot(
                                function_name=func,
                                file_path="ECommerceAPI.java",
                                line_number=None,
                                self_time_ms=samples * 0.5,
                                total_time_ms=samples * 0.5,
                                call_count=samples,
                                percentage=pct,
                            )
                        )
                    except (ValueError, IndexError):
                        continue

        return (
            sorted(hotspots, key=lambda h: h.call_count, reverse=True)[:10]
            if hotspots
            else JavaProfiler._generate_hotspots(5000.0)
        )

    @staticmethod
    def _fallback_profile(execution_time_ms: float) -> ProfileResult:
        """Generate simulated hotspot data when real profiling fails."""
        hotspots = JavaProfiler._generate_hotspots(execution_time_ms)
        return ProfileResult(
            success=True,
            execution_time_ms=execution_time_ms,
            hotspots=hotspots,
            output="(simulated - async-profiler not available)",
        )

    @staticmethod
    def profile_request(port: int = JAVA_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile Java application by making requests and measuring time."""
        import httpx

        execution_times = []
        try:
            for _ in range(duration * 2):
                req_start = time.time()
                try:
                    response = httpx.get(
                        f"http://localhost:{port}/catalog", timeout=5.0
                    )
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = (
                sum(execution_times) / len(execution_times) if execution_times else 0.0
            )
            hotspots = JavaProfiler._generate_hotspots(avg_time)

            return ProfileResult(
                success=True,
                execution_time_ms=avg_time,
                hotspots=hotspots,
                output=f"Average execution time: {avg_time:.2f}ms",
            )
        except Exception as e:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=str(e),
            )

    @staticmethod
    def _generate_hotspots(execution_time_ms: float) -> List[Hotspot]:
        """Generate simulated hotspot data based on execution time."""
        hotspots = []
        total_time = execution_time_ms

        hotspot_configs = [
            ("buildCatalogResponse", "ECommerceAPI.java", 84, 0.32),
            ("findProductLinear", "ECommerceAPI.java", 75, 0.25),
            ("calculateOrderTotal", "ECommerceAPI.java", 98, 0.18),
            ("deepCopyProduct", "ECommerceAPI.java", 113, 0.12),
            ("filterByCategory", "ECommerceAPI.java", 123, 0.08),
        ]

        for func_name, file_path, line, impact in hotspot_configs:
            self_time = total_time * impact
            hotspots.append(
                Hotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=line,
                    self_time_ms=self_time,
                    total_time_ms=self_time * 1.3,
                    call_count=int(150 * (1 - impact * 0.5)),
                    percentage=impact * 100,
                )
            )

        return hotspots


class CppProfiler:
    """Profiler for C++ code using Linux perf."""

    @staticmethod
    def profile_with_perf(binary_path: str = None, duration: int = 5) -> ProfileResult:
        """
        Profile C++ binary using Linux perf.

        Perf is a sampling profiler that uses hardware performance counters
        to sample stack traces at regular intervals.

        Usage: perf record -g -o <output.perf> -- <binary>
               perf report -i <output.perf> --stdio
        """
        if binary_path is None:
            binary_path = CPP_BINARY

        if not os.path.exists(binary_path):
            logger.warning(f"Binary not found: {binary_path}, compiling...")
            if not CppProfiler._compile_cpp():
                avg_time = measure_console_execution_time(
                    [CPP_BINARY], warmup_runs=1, measure_runs=3
                )
                return CppProfiler._fallback_profile(
                    avg_time if avg_time > 0 else duration * 1000.0
                )
            binary_path = CPP_BINARY

        with tempfile.NamedTemporaryFile(suffix=".perf", delete=False) as f:
            perf_data_file = f.name

        try:
            result = subprocess.run(
                ["perf", "record", "-g", "-o", perf_data_file, "--", binary_path],
                capture_output=True,
                timeout=duration + 30,
            )

            if result.returncode == 0 and os.path.exists(perf_data_file):
                report_result = subprocess.run(
                    [
                        "perf",
                        "report",
                        "-i",
                        perf_data_file,
                        "--stdio",
                        "-n",
                        "-g",
                        "none",
                    ],
                    capture_output=True,
                    timeout=30,
                )

                if report_result.returncode == 0:
                    output = report_result.stdout.decode("utf-8", errors="replace")
                    hotspots = CppProfiler._parse_perf_output(output)
                    return ProfileResult(
                        success=True,
                        execution_time_ms=duration * 1000.0,
                        hotspots=hotspots,
                        output=output[:1000],
                    )

            logger.warning("perf failed, falling back to simulated")
            avg_time = measure_console_execution_time(
                [binary_path], warmup_runs=1, measure_runs=3
            )
            return CppProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )

        except subprocess.TimeoutExpired:
            logger.warning("perf timed out, measuring actual C++ execution time")
            avg_time = measure_console_execution_time(
                [binary_path], warmup_runs=1, measure_runs=3
            )
            return CppProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )
        except FileNotFoundError:
            logger.warning("perf not found, measuring actual C++ execution time")
            avg_time = measure_console_execution_time(
                [binary_path], warmup_runs=1, measure_runs=3
            )
            return CppProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )
        except Exception as e:
            logger.warning(f"perf error: {e}, measuring actual C++ execution time")
            avg_time = measure_console_execution_time(
                [binary_path], warmup_runs=1, measure_runs=3
            )
            return CppProfiler._fallback_profile(
                avg_time if avg_time > 0 else duration * 1000.0
            )
        finally:
            if os.path.exists(perf_data_file):
                os.unlink(perf_data_file)

    @staticmethod
    def _compile_cpp() -> bool:
        """Compile C++ source code."""
        try:
            main_cpp = os.path.join(CPP_SRC_PATH, "main.cpp")
            build_dir = os.path.join(CPP_SRC_PATH, "build")
            os.makedirs(build_dir, exist_ok=True)

            result = subprocess.run(
                ["g++", "-g", "-O0", "-o", CPP_BINARY, main_cpp],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"C++ compilation failed: {e}")
            return False

    @staticmethod
    def _parse_perf_output(output: str) -> List[Hotspot]:
        """Parse perf report text output."""
        hotspots = []
        seen_funcs = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            try:
                if parts[0].replace(".", "").replace("%", "").isdigit():
                    pass
                elif any(c.isdigit() for c in parts[0]):
                    pass
                else:
                    continue
            except (ValueError, IndexError):
                continue

            try:
                func_name = None
                file_path = "main.cpp"
                self_time = 0.0

                if "[" in line and "]" in line:
                    idx = line.find("]")
                    after = line[idx + 1 :].strip()
                    func_parts = after.split()
                    if func_parts:
                        func_name = func_parts[0].split("(")[0]
                        if "(" in func_parts[0]:
                            file_path = func_parts[0].split("(")[1].rstrip(")")
                elif any(c.isdigit() for c in parts[0]):
                    for i, part in enumerate(parts):
                        if ":" in part and not part.startswith(":"):
                            func_part = part.rstrip(":")
                            if func_part:
                                func_name = func_part
                                file_path = func_part
                                break

                if not func_name:
                    continue

                if func_name in seen_funcs:
                    seen_funcs[func_name].call_count += 1
                    seen_funcs[func_name].self_time_ms += 1.0
                else:
                    seen_funcs[func_name] = Hotspot(
                        function_name=func_name,
                        file_path=file_path,
                        line_number=None,
                        self_time_ms=1.0,
                        total_time_ms=1.0,
                        call_count=1,
                        percentage=0.0,
                    )
            except (ValueError, IndexError):
                continue

        hotspots = list(seen_funcs.values())
        if not hotspots:
            return CppProfiler._generate_hotspots(5000.0)

        total_samples = sum(h.call_count for h in hotspots) or 1
        total_time = sum(h.self_time_ms for h in hotspots) or 1
        for h in hotspots:
            h.percentage = (h.self_time_ms / total_time) * 100
            h.total_time_ms = h.self_time_ms * 1.1

        return sorted(hotspots, key=lambda h: h.self_time_ms, reverse=True)[:10]

    @staticmethod
    def _fallback_profile(execution_time_ms: float) -> ProfileResult:
        """Generate simulated hotspot data when real profiling fails."""
        hotspots = CppProfiler._generate_hotspots(execution_time_ms)
        return ProfileResult(
            success=True,
            execution_time_ms=execution_time_ms,
            hotspots=hotspots,
            output="(simulated - perf not available)",
        )

    @staticmethod
    def profile_request(port: int = CPP_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile C++ application by making requests and measuring time."""
        import httpx

        execution_times = []
        try:
            for _ in range(duration * 2):
                req_start = time.time()
                try:
                    response = httpx.get(
                        f"http://localhost:{port}/catalog", timeout=5.0
                    )
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = (
                sum(execution_times) / len(execution_times) if execution_times else 0.0
            )
            hotspots = CppProfiler._generate_hotspots(avg_time)

            return ProfileResult(
                success=True,
                execution_time_ms=avg_time,
                hotspots=hotspots,
                output=f"Average execution time: {avg_time:.2f}ms",
            )
        except Exception as e:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=str(e),
            )

    @staticmethod
    def _generate_hotspots(execution_time_ms: float) -> List[Hotspot]:
        """Generate simulated hotspot data based on execution time."""
        hotspots = []
        total_time = execution_time_ms

        hotspot_configs = [
            ("build_catalog_response", "main.cpp", 64, 0.30),
            ("find_product_linear", "main.cpp", 55, 0.26),
            ("calculate_order_total", "main.cpp", 75, 0.19),
            ("deep_copy_product", "main.cpp", 88, 0.11),
            ("format_product_json", "main.cpp", 111, 0.07),
        ]

        for func_name, file_path, line, impact in hotspot_configs:
            self_time = total_time * impact
            hotspots.append(
                Hotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=line,
                    self_time_ms=self_time,
                    total_time_ms=self_time * 1.3,
                    call_count=int(150 * (1 - impact * 0.5)),
                    percentage=impact * 100,
                )
            )

        return hotspots


class ProfileRunner:
    """Unified profile runner for all languages."""

    @staticmethod
    def profile(
        language: str, duration: int = 5, use_real_profiler: bool = True
    ) -> ProfileResult:
        """
        Profile code for a specific language.

        Args:
            language: 'python', 'java', or 'cpp'
            duration: profiling duration in seconds
            use_real_profiler: if True, try real profiler first, fallback to simulated
        """
        language = language.lower()

        if language == "python":
            if use_real_profiler:
                return PythonProfiler.profile_with_austin(duration=duration)
            return PythonProfiler.profile_request(duration=duration)
        elif language == "java":
            if use_real_profiler:
                return JavaProfiler.profile_with_async_profiler(duration=duration)
            return JavaProfiler.profile_request(duration=duration)
        elif language == "cpp":
            if use_real_profiler:
                return CppProfiler.profile_with_perf(duration=duration)
            return CppProfiler.profile_request(duration=duration)
        else:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=f"Unsupported language: {language}",
            )

    @staticmethod
    def measure_request_time(language: str, num_requests: int = 5) -> float:
        """Measure average request time for a language."""
        port_map = {
            "python": PYTHON_API_PORT,
            "java": JAVA_API_PORT,
            "cpp": CPP_API_PORT,
        }

        import httpx

        port = port_map.get(language.lower(), PYTHON_API_PORT)
        times = []

        for _ in range(num_requests):
            try:
                start = time.time()
                httpx.get(f"http://localhost:{port}/catalog", timeout=10.0)
                times.append((time.time() - start) * 1000)
            except Exception:
                pass

        return sum(times) / len(times) if times else 0.0
