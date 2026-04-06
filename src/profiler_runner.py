"""Profiler runner for different languages."""

import subprocess
import os
import tempfile
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ProfileResult:
    """Result from profiling a binary/script."""

    success: bool
    output: str
    error: Optional[str]
    execution_time_ms: float
    hotspots: list


class ProfilerRunner:
    """Base class for profiler runners."""

    def profile(
        self, target_path: str, duration_seconds: int = 10, output_path: Optional[str] = None
    ) -> ProfileResult:
        """Run profiler on target."""
        raise NotImplementedError

    def parse_output(self, output: str) -> list:
        """Parse profiler output to extract hotspots."""
        raise NotImplementedError


class PythonProfiler(ProfilerRunner):
    """Profiler for Python using Austin or py-spy."""

    def __init__(self, profiler: str = "austin"):
        self.profiler = profiler

    def profile(
        self, script_path: str, duration_seconds: int = 10, output_path: Optional[str] = None
    ) -> ProfileResult:
        """Profile a Python script."""
        start_time = time.time()

        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mojo")

        try:
            if self.profiler == "austin":
                cmd = [
                    "austin",
                    "-x",
                    str(duration_seconds),
                    "-o",
                    output_path,
                    "python",
                    script_path,
                ]
            else:
                cmd = [
                    "py-spy",
                    "record",
                    "-o",
                    output_path.replace(".mojo", ".html"),
                    "--",
                    "python",
                    script_path,
                ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=duration_seconds + 30
            )

            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0:
                with open(output_path, "r") as f:
                    output = f.read()
                return ProfileResult(
                    success=True,
                    output=output,
                    error=None,
                    execution_time_ms=execution_time,
                    hotspots=self.parse_output(output),
                )
            else:
                return ProfileResult(
                    success=False,
                    output="",
                    error=result.stderr,
                    execution_time_ms=execution_time,
                    hotspots=[],
                )

        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                output="",
                error="Profile timed out",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )
        except FileNotFoundError as e:
            return ProfileResult(
                success=False,
                output="",
                error=f"Profiler not found: {e}",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )

    def parse_output(self, output: str) -> list:
        """Parse Austin MOJO or text output."""
        hotspots = []

        for line in output.split("\n"):
            if not line or line.startswith("#"):
                continue

            parts = line.split(";")
            if len(parts) < 2:
                continue

            try:
                stack = parts[0].strip()
                samples = int(parts[-1].strip()) if parts[-1].strip().isdigit() else 0

                func_name = stack.split("->")[-1].strip() if "->" in stack else stack

                hotspots.append({"function": func_name, "samples": samples, "stack": stack})
            except (ValueError, IndexError):
                continue

        return sorted(hotspots, key=lambda x: x["samples"], reverse=True)[:10]


class CppProfiler(ProfilerRunner):
    """Profiler for C++ using Austin or gperftools."""

    def __init__(self, profiler: str = "austin"):
        self.profiler = profiler

    def profile(
        self, binary_path: str, duration_seconds: int = 10, output_path: Optional[str] = None
    ) -> ProfileResult:
        """Profile a C++ binary."""
        start_time = time.time()

        if output_path is None:
            output_path = tempfile.mktemp(suffix=".prof")

        try:
            if self.profiler == "austin":
                cmd = ["austin", "-x", str(duration_seconds), "-o", output_path, binary_path]
            else:
                cmd = ["google-pprof", "--text", binary_path, output_path]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=duration_seconds + 30
            )

            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0:
                return ProfileResult(
                    success=True,
                    output=result.stdout,
                    error=None,
                    execution_time_ms=execution_time,
                    hotspots=self.parse_output(result.stdout),
                )
            else:
                return ProfileResult(
                    success=False,
                    output="",
                    error=result.stderr,
                    execution_time_ms=execution_time,
                    hotspots=[],
                )

        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                output="",
                error="Profile timed out",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )
        except FileNotFoundError as e:
            return ProfileResult(
                success=False,
                output="",
                error=f"Profiler not found: {e}",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )

    def parse_output(self, output: str) -> list:
        """Parse gperftools/Austin output."""
        hotspots = []

        for line in output.split("\n"):
            if not line or line.startswith("Total:") or line.startswith("---"):
                continue

            parts = line.split()
            if len(parts) < 4:
                continue

            try:
                percentage = float(parts[0].replace("%", ""))
                samples = int(parts[1])
                func_name = parts[3] if len(parts) > 3 else "unknown"

                hotspots.append(
                    {"function": func_name, "percentage": percentage, "samples": samples}
                )
            except (ValueError, IndexError):
                continue

        return sorted(hotspots, key=lambda x: x.get("percentage", 0), reverse=True)[:10]


class JavaProfiler(ProfilerRunner):
    """Profiler for Java using async-profiler."""

    def __init__(self, profiler_path: Optional[str] = None):
        self.profiler_path = profiler_path or "build/bin/asprof"

    def profile(
        self, jar_path: str, duration_seconds: int = 10, output_path: Optional[str] = None
    ) -> ProfileResult:
        """Profile a Java application."""
        start_time = time.time()

        if output_path is None:
            output_path = tempfile.mktemp(suffix=".html")

        pid = self._get_java_pid(jar_path)
        if not pid:
            return ProfileResult(
                success=False,
                output="",
                error="Could not find Java process",
                execution_time_ms=0,
                hotspots=[],
            )

        try:
            cmd = [
                self.profiler_path,
                "-d",
                str(duration_seconds),
                "-f",
                output_path,
                "-e",
                "cpu",
                pid,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=duration_seconds + 30
            )

            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0:
                return ProfileResult(
                    success=True,
                    output=result.stdout,
                    error=None,
                    execution_time_ms=execution_time,
                    hotspots=self.parse_output(result.stdout),
                )
            else:
                return ProfileResult(
                    success=False,
                    output="",
                    error=result.stderr,
                    execution_time_ms=execution_time,
                    hotspots=[],
                )

        except subprocess.TimeoutExpired:
            return ProfileResult(
                success=False,
                output="",
                error="Profile timed out",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )
        except FileNotFoundError as e:
            return ProfileResult(
                success=False,
                output="",
                error=f"Profiler not found: {e}",
                execution_time_ms=(time.time() - start_time) * 1000,
                hotspots=[],
            )

    def _get_java_pid(self, jar_path: str) -> Optional[str]:
        """Get PID of running Java process for jar."""
        try:
            result = subprocess.run(["pgrep", "-f", jar_path], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    def parse_output(self, output: str) -> list:
        """Parse async-profiler text output."""
        hotspots = []

        for line in output.split("\n"):
            if not line or "---" in line or "CPU" in line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                if "%" in parts[0]:
                    percentage = float(parts[0].replace("%", ""))
                    func_part = " ".join(parts[1:])

                    if "(" in func_part:
                        func_name = func_part.split("(")[0].strip()
                    else:
                        func_name = func_part

                    hotspots.append({"function": func_name, "percentage": percentage})
            except (ValueError, IndexError):
                continue

        return sorted(hotspots, key=lambda x: x.get("percentage", 0), reverse=True)[:10]


def get_profiler_runner(language: str, **kwargs) -> ProfilerRunner:
    """Factory function to get appropriate profiler runner."""
    profilers = {
        "python": PythonProfiler,
        "cpp": CppProfiler,
        "java": JavaProfiler,
    }

    profiler_class = profilers.get(language.lower())
    if profiler_class is None:
        raise ValueError(f"Unsupported language: {language}")

    return profiler_class(**kwargs)
