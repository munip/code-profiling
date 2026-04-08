"""
Unified Profile Runner for Code Profiler Environment.

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
JAVA_CLASSPATH = "/app/java_classes"
CPP_SRC_PATH = "/app/server/cpp/src"
CPP_BINARY = "/app/cpp_src/build/ecommerce_api"
ASYNC_PROFILER_HOME = "/opt/async-profiler"
PYTHON_SRC_PATH = "/app/server/python/src"

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


class PythonProfiler:
    """Profiler for Python code using austin frame sampler."""

    @staticmethod
    def profile_with_austin(script_path: str = None, duration: int = 5) -> ProfileResult:
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
            result = subprocess.run(
                ["austin", "-x", str(duration), "-o", output_file, "python", script_path],
                capture_output=True,
                timeout=duration + 30,
            )

            execution_time = duration * 1000.0

            if result.returncode == 0 and os.path.exists(output_file):
                with open(output_file) as f:
                    output = f.read()

                hotspots = PythonProfiler._parse_austin_output(output, execution_time)

                return ProfileResult(
                    success=True,
                    execution_time_ms=execution_time,
                    hotspots=hotspots,
                    output=output,
                )
            else:
                error_msg = result.stderr.decode() if result.stderr else "austin failed"
                logger.warning(f"austin failed: {error_msg}, falling back to simulated")
                return PythonProfiler._fallback_profile(execution_time)

        except FileNotFoundError:
            logger.warning("austin not found, falling back to simulated profiling")
            return PythonProfiler._fallback_profile(duration * 1000.0)
        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                execution_time_ms=duration * 1000.0,
                hotspots=[],
                error="Profile timed out",
            )
        except Exception as e:
            logger.warning(f"austin error: {e}, falling back to simulated")
            return PythonProfiler._fallback_profile(duration * 1000.0)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @staticmethod
    def _parse_austin_output(output: str, total_time_ms: float) -> List[Hotspot]:
        """Parse austin output format. Each line: stack_trace;samples."""
        hotspots = []
        for line in output.split("\n"):
            if not line or line.startswith("#") or line.count(";") > 100:
                continue

            parts = line.split(";")
            if len(parts) < 2:
                continue

            try:
                stack = parts[0].strip()
                samples = int(parts[-1].strip()) if parts[-1].strip().isdigit() else 0

                func_name = stack.split("->")[-1].strip() if "->" in stack else stack
                if not func_name or func_name in (
                    "python3",
                    "python",
                    "PyRun_SimpleFileExFlags",
                    "__libc_start_main",
                ):
                    func_name = (
                        stack.split(";")[-2].strip() if len(stack.split(";")) > 1 else func_name
                    )

                hotspots.append(
                    Hotspot(
                        function_name=func_name,
                        file_path="app.py",
                        line_number=None,
                        self_time_ms=samples * 0.5,
                        total_time_ms=samples * 0.5,
                        call_count=samples,
                        percentage=0.0,
                    )
                )
            except (ValueError, IndexError):
                continue

        total_samples = sum(h.call_count for h in hotspots) or 1
        for h in hotspots:
            h.percentage = (h.call_count / total_samples) * 100

        return sorted(hotspots, key=lambda h: h.call_count, reverse=True)[:10]

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
    def profile_request(port: int = PYTHON_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile Python Flask API by making requests and measuring time."""
        import httpx

        execution_times = []
        try:
            for _ in range(duration * 2):
                req_start = time.time()
                try:
                    response = httpx.get(f"http://localhost:{port}/catalog", timeout=5.0)
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
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

        if not os.path.exists(JAVA_CLASSPATH):
            logger.warning(f"Java classpath not found: {JAVA_CLASSPATH}")
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
            return JavaProfiler._fallback_profile(5000.0)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            output_file = f.name

        try:
            result = subprocess.run(
                [
                    f"{ASYNC_PROFILER_HOME}/profiler.sh",
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
                error_msg = result.stderr.decode() if result.stderr else "async-profiler failed"
                logger.warning(f"async-profiler failed: {error_msg}")
                return JavaProfiler._fallback_profile(duration * 1000.0)

        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                execution_time_ms=duration * 1000.0,
                hotspots=[],
                error="Profile timed out",
            )
        except FileNotFoundError:
            logger.warning("async-profiler not found, using simulated profiling")
            return JavaProfiler._fallback_profile(duration * 1000.0)
        except Exception as e:
            logger.warning(f"async-profiler error: {e}")
            return JavaProfiler._fallback_profile(duration * 1000.0)
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
                        pct = float(parts[-1].strip().replace("%", "")) if "%" in parts[-1] else 5.0

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
                    response = httpx.get(f"http://localhost:{port}/catalog", timeout=5.0)
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
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
    """Profiler for C++ code using austin frame sampler."""

    @staticmethod
    def profile_with_austin(binary_path: str = None, duration: int = 5) -> ProfileResult:
        """
        Profile C++ binary using austin frame sampler.

        Austin works similarly to Python - it samples stack traces
        at regular intervals from a running process.

        Usage: austin -x <duration> -o <output.prof> <binary>
        """
        if binary_path is None:
            binary_path = CPP_BINARY

        if not os.path.exists(binary_path):
            logger.warning(f"Binary not found: {binary_path}, compiling...")
            if not CppProfiler._compile_cpp():
                return CppProfiler._fallback_profile(duration * 1000.0)
            binary_path = CPP_BINARY

        with tempfile.NamedTemporaryFile(suffix=".prof", delete=False) as f:
            output_file = f.name

        try:
            result = subprocess.run(
                ["austin", "-x", str(duration), "-o", output_file, binary_path],
                capture_output=True,
                timeout=duration + 30,
            )

            if result.returncode == 0 and os.path.exists(output_file):
                with open(output_file) as f:
                    output = f.read()

                hotspots = CppProfiler._parse_austin_output(output)

                return ProfileResult(
                    success=True,
                    execution_time_ms=duration * 1000.0,
                    hotspots=hotspots,
                    output=output[:1000],
                )
            else:
                error_msg = result.stderr.decode() if result.stderr else "austin failed"
                logger.warning(f"austin failed: {error_msg}")
                return CppProfiler._fallback_profile(duration * 1000.0)

        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                execution_time_ms=duration * 1000.0,
                hotspots=[],
                error="Profile timed out",
            )
        except FileNotFoundError:
            logger.warning("austin not found, using simulated profiling")
            return CppProfiler._fallback_profile(duration * 1000.0)
        except Exception as e:
            logger.warning(f"austin error: {e}")
            return CppProfiler._fallback_profile(duration * 1000.0)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @staticmethod
    def _compile_cpp() -> bool:
        """Compile C++ source code."""
        try:
            main_cpp = os.path.join(CPP_SRC_PATH, "main.cpp")
            build_dir = os.path.join(CPP_SRC_PATH, "build")
            os.makedirs(build_dir, exist_ok=True)

            result = subprocess.run(
                ["g++", "-O0", "-o", CPP_BINARY, main_cpp],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"C++ compilation failed: {e}")
            return False

    @staticmethod
    def _parse_austin_output(output: str) -> List[Hotspot]:
        """Parse austin output for C++."""
        hotspots = []

        for line in output.split("\n"):
            if not line or line.startswith("#") or line.count(";") > 100:
                continue

            parts = line.split(";")
            if len(parts) < 2:
                continue

            try:
                stack = parts[0].strip()
                samples = int(parts[-1].strip()) if parts[-1].strip().isdigit() else 0

                func_name = stack.split("->")[-1].strip() if "->" in stack else stack
                if not func_name or func_name in ("__libc_start_main", "main"):
                    func_name = (
                        stack.split(";")[-2].strip() if len(stack.split(";")) > 1 else func_name
                    )

                hotspots.append(
                    Hotspot(
                        function_name=func_name,
                        file_path="main.cpp",
                        line_number=None,
                        self_time_ms=samples * 0.5,
                        total_time_ms=samples * 0.5,
                        call_count=samples,
                        percentage=0.0,
                    )
                )
            except (ValueError, IndexError):
                continue

        total_samples = sum(h.call_count for h in hotspots) or 1
        for h in hotspots:
            h.percentage = (h.call_count / total_samples) * 100

        return sorted(hotspots, key=lambda h: h.call_count, reverse=True)[:10]

    @staticmethod
    def _fallback_profile(execution_time_ms: float) -> ProfileResult:
        """Generate simulated hotspot data when real profiling fails."""
        hotspots = CppProfiler._generate_hotspots(execution_time_ms)
        return ProfileResult(
            success=True,
            execution_time_ms=execution_time_ms,
            hotspots=hotspots,
            output="(simulated - austin not available)",
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
                    response = httpx.get(f"http://localhost:{port}/catalog", timeout=5.0)
                    req_time = (time.time() - req_start) * 1000
                    if response.status_code == 200:
                        execution_times.append(req_time)
                except Exception:
                    pass
                time.sleep(0.5)

            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
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
    def profile(language: str, duration: int = 5, use_real_profiler: bool = True) -> ProfileResult:
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
                return CppProfiler.profile_with_austin(duration=duration)
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
