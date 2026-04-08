"""
Unified Profile Runner for Code Profiler Environment.

Provides profiling capabilities for Python, Java, and C++ code.
"""

import subprocess
import time
import tempfile
import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

JAVA_MAIN_CLASS = "com.ecommerce.api.ECommerceAPI"
JAVA_CLASSPATH = "/app/java_classes"
CPP_BINARY = "/app/cpp_src/build/ecommerce_api"
ASYNC_PROFILER_HOME = "/opt/async-profiler"

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
    """Profiler for Python code using py-spy or time-based measurement."""

    @staticmethod
    def profile_request(port: int = PYTHON_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile Python Flask API by making requests and measuring time."""
        import httpx

        start_time = time.time()
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

    @staticmethod
    def profile_request(port: int = JAVA_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile Java application by making requests and measuring time."""
        import httpx

        start_time = time.time()
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
    def profile_with_async_profiler(duration: int = 5) -> ProfileResult:
        """Profile Java using async-profiler."""
        if not os.path.exists(ASYNC_PROFILER_HOME):
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error="async-profiler not installed",
            )

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
                    "java",
                    "-cp",
                    JAVA_CLASSPATH,
                    JAVA_MAIN_CLASS,
                ],
                capture_output=True,
                timeout=duration + 30,
            )

            return ProfileResult(
                success=result.returncode == 0,
                execution_time_ms=0.0,
                hotspots=[],
                output=result.stdout.decode() if result.stdout else "",
                error=result.stderr.decode() if result.stderr else None,
            )
        except Exception as e:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=str(e),
            )
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

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
    """Profiler for C++ code."""

    @staticmethod
    def profile_request(port: int = CPP_API_PORT, duration: int = 5) -> ProfileResult:
        """Profile C++ application by making requests and measuring time."""
        import httpx

        start_time = time.time()
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
    def profile_with_austin(binary_path: str = CPP_BINARY, duration: int = 5) -> ProfileResult:
        """Profile C++ binary using austin."""
        if not os.path.exists(binary_path):
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=f"Binary not found: {binary_path}",
            )

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
                return ProfileResult(
                    success=True,
                    execution_time_ms=0.0,
                    hotspots=CppProfiler._parse_austin_output(output),
                    output=output,
                )

            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=result.stderr.decode() if result.stderr else "austin failed",
            )
        except Exception as e:
            return ProfileResult(
                success=False,
                execution_time_ms=0.0,
                hotspots=[],
                error=str(e),
            )
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @staticmethod
    def _parse_austin_output(output: str) -> List[Hotspot]:
        """Parse austin output to extract hotspots."""
        hotspots = []
        for line in output.split("\n"):
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if len(parts) >= 2:
                try:
                    stack = parts[0].strip()
                    func_name = stack.split("->")[-1].strip() if "->" in stack else stack
                    samples = int(parts[-1].strip()) if parts[-1].strip().isdigit() else 0
                    hotspots.append(
                        Hotspot(
                            function_name=func_name,
                            file_path="main.cpp",
                            line_number=None,
                            self_time_ms=samples * 0.5,
                            total_time_ms=samples * 0.5,
                            call_count=samples,
                            percentage=5.0,
                        )
                    )
                except (ValueError, IndexError):
                    continue

        return sorted(hotspots, key=lambda h: h.call_count, reverse=True)[:10]

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
    def profile(language: str, duration: int = 5) -> ProfileResult:
        """Profile code for a specific language."""
        language = language.lower()

        if language == "python":
            return PythonProfiler.profile_request(duration=duration)
        elif language == "java":
            return JavaProfiler.profile_request(duration=duration)
        elif language == "cpp":
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
