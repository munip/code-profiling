"""Hotspot analyzer for profiler output."""

import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ParsedHotspot:
    """Parsed hotspot data from profiler output."""

    function_name: str
    file_path: Optional[str]
    line_number: Optional[int]
    self_time: float
    total_time: float
    call_count: int
    percentage: float


class HotspotAnalyzer:
    """Analyzes profiler output to extract hotspots."""

    def parse_flamegraph(self, output: str) -> List[ParsedHotspot]:
        """Parse flamegraph-style profiler output."""
        hotspots = []
        lines = output.strip().split("\n")

        for line in lines:
            if not line or line.startswith("#") or line.startswith(" "):
                continue

            parts = line.split(";")
            if not parts:
                continue

            func_info = parts[0].strip()

            match = re.match(r"([\w:]+)\s+\(([^)]+)\)", func_info)
            if match:
                func_name = match.group(1)
                file_path = match.group(2)
            else:
                func_name = func_info
                file_path = None

            percentage = 0.0
            self_time = 0.0
            total_time = 0.0
            call_count = 0

            for part in parts[1:]:
                part = part.strip()
                if "samples" in part or "ms" in part:
                    try:
                        val = float(re.search(r"[\d.]+", part).group())
                        if "self" in part.lower():
                            self_time = val
                        else:
                            total_time = val
                    except (ValueError, AttributeError):
                        pass
                elif re.match(r"^\d+$", part):
                    call_count = int(part)

            hotspots.append(
                ParsedHotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=None,
                    self_time=self_time,
                    total_time=total_time,
                    call_count=call_count,
                    percentage=percentage,
                )
            )

        return hotspots

    def parse_austin_output(self, output: str) -> List[ParsedHotspot]:
        """Parse Austin profiler text output."""
        hotspots = []

        pattern = re.compile(
            r"^(\d+)\s+([^:]+):(\d+):([^\s]+)\s+\[([^\]]+)\]\s*(\d+)?", re.MULTILINE
        )

        for match in pattern.finditer(output):
            samples = int(match.group(1))
            file_path = match.group(2)
            line_number = int(match.group(3))
            func_name = match.group(4)
            module = match.group(5)

            hotspots.append(
                ParsedHotspot(
                    function_name=func_name,
                    file_path=file_path,
                    line_number=line_number,
                    self_time=samples,
                    total_time=samples,
                    call_count=1,
                    percentage=0.0,
                )
            )

        return hotspots

    def parse_async_profiler_text(self, output: str) -> List[ParsedHotspot]:
        """Parse async-profiler text output."""
        hotspots = []

        lines = output.strip().split("\n")
        for line in lines:
            if not line or line.startswith("---") or line.startswith("CPU"):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            try:
                if "%" in parts[0]:
                    percentage = float(parts[0].replace("%", ""))
                else:
                    continue

                samples_match = re.search(r"\d+", parts[1])
                samples = int(samples_match.group()) if samples_match else 0

                func_match = re.search(r"\[([^\]]+)\]", line)
                func_info = func_match.group(1) if func_match else parts[-1]

                func_parts = func_info.rsplit(".", 1)
                func_name = func_parts[-1] if len(func_parts) > 1 else func_info

                hotspots.append(
                    ParsedHotspot(
                        function_name=func_name,
                        file_path=None,
                        line_number=None,
                        self_time=samples * 0.01,
                        total_time=samples * 0.01,
                        call_count=1,
                        percentage=percentage,
                    )
                )
            except (ValueError, IndexError):
                continue

        return hotspots

    def find_top_hotspots(
        self, hotspots: List[ParsedHotspot], top_n: int = 5
    ) -> List[ParsedHotspot]:
        """Get top N hotspots by self time."""
        sorted_hotspots = sorted(hotspots, key=lambda h: h.self_time, reverse=True)
        return sorted_hotspots[:top_n]

    def generate_fix_suggestion(self, hotspot: ParsedHotspot) -> str:
        """Generate a suggested fix based on hotspot characteristics."""
        func_lower = hotspot.function_name.lower()

        suggestions = []

        if "concat" in func_lower or "string" in func_lower:
            suggestions.append(
                f"Consider using StringBuilder/StringBuffer or f-strings "
                f"instead of string concatenation in {hotspot.function_name}"
            )

        if "join" in func_lower:
            suggestions.append(
                f"Review join operation in {hotspot.function_name} - "
                f"may be creating unnecessary intermediate collections"
            )

        if "sort" in func_lower:
            suggestions.append(
                f"Consider using a more efficient sorting algorithm or "
                f"caching sorted results in {hotspot.function_name}"
            )

        if "search" in func_lower or "find" in func_lower:
            suggestions.append(
                f"Consider using a hash-based lookup (dict/set) instead of "
                f"linear search in {hotspot.function_name}"
            )

        if "loop" in func_lower or hotspot.call_count > 1000:
            suggestions.append(
                f"High call count ({hotspot.call_count}) detected - "
                f"consider caching or memoization in {hotspot.function_name}"
            )

        if not suggestions:
            suggestions.append(f"Analyze {hotspot.function_name} for algorithmic improvements")

        return " ".join(suggestions)
