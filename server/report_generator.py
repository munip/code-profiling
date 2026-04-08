"""
Report Generator for Code Profiler Environment.

Generates improvement reports from iteration results.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class IterationRecord:
    """Record of a single iteration's results."""

    iteration: int
    outcome: str
    delta_percent: float
    rebuilt: bool
    tag: str
    status: str
    execution_time_ms: float = 0.0
    reward: float = 0.0


@dataclass
class EpisodeReport:
    """Complete episode report."""

    language: str
    baseline_ms: float
    final_ms: float
    improvement_percent: float
    iterations: List[IterationRecord]
    before_code: str
    after_code: str
    rebuild_tags: List[str]
    total_reward: float
    generated_at: datetime


class ReportGenerator:
    """Generates markdown improvement reports."""

    TEMPLATE = """# Code Profiling Improvement Report
Generated: {timestamp}

## {language}

**Baseline**: {baseline_ms}ms | **Final**: {final_ms}ms | **Improvement**: {improvement_percent}%

### Iteration Summary

| Iteration | Outcome | Delta | Rebuilt | Tag | Status |
|-----------|---------|-------|---------|-----|--------|
{iteration_rows}

### Final Comparison (vs ORIGINAL from baseline)

#### build_catalog_response

**Before:**
```{language}
{before_code}
```

**After:**
```{language}
{after_code}
```

---

**Total Reward**: {total_reward:+.3f}
**Rebuild Tags**: {rebuild_tags}

"""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def generate_report(self, report: EpisodeReport) -> str:
        """Generate a markdown report from episode results."""
        iteration_rows = []
        for r in report.iterations:
            iteration_rows.append(
                f"| {r.iteration} | {r.outcome} | {r.delta_percent:+.2f}% | "
                f"{'Yes' if r.rebuilt else 'No'} | {r.tag or '-'} | {r.status} |"
            )

        iteration_table = "\n".join(iteration_rows)

        content = self.TEMPLATE.format(
            timestamp=report.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            language=report.language.upper(),
            baseline_ms=report.baseline_ms,
            final_ms=report.final_ms,
            improvement_percent=f"{report.improvement_percent:+.2f}%",
            iteration_rows=iteration_table,
            before_code=report.before_code.strip(),
            after_code=report.after_code.strip(),
            total_reward=report.total_reward,
            rebuild_tags=", ".join(report.rebuild_tags) if report.rebuild_tags else "None",
        )

        return content

    def save_report(self, report: EpisodeReport, filename: str = None) -> Path:
        """Save report to file."""
        content = self.generate_report(report)

        if filename is None:
            timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
            filename = f"{report.language}_{timestamp}.md"

        filepath = self.output_dir / filename
        filepath.write_text(content)
        return filepath

    def create_iteration_record(
        self,
        iteration: int,
        outcome: str,
        delta_percent: float,
        rebuilt: bool,
        tag: str,
        status: str,
        execution_time_ms: float = 0.0,
        reward: float = 0.0,
    ) -> IterationRecord:
        """Create an iteration record."""
        return IterationRecord(
            iteration=iteration,
            outcome=outcome,
            delta_percent=delta_percent,
            rebuilt=rebuilt,
            tag=tag,
            status=status,
            execution_time_ms=execution_time_ms,
            reward=reward,
        )


def create_episode_report(
    language: str,
    baseline_ms: float,
    final_ms: float,
    iterations: List[IterationRecord],
    before_code: str = "",
    after_code: str = "",
    rebuild_tags: List[str] = None,
    total_reward: float = 0.0,
) -> EpisodeReport:
    """Create an episode report."""
    if rebuild_tags is None:
        rebuild_tags = []

    improvement_percent = ((baseline_ms - final_ms) / baseline_ms * 100) if baseline_ms > 0 else 0

    return EpisodeReport(
        language=language,
        baseline_ms=baseline_ms,
        final_ms=final_ms,
        improvement_percent=improvement_percent,
        iterations=iterations,
        before_code=before_code,
        after_code=after_code,
        rebuild_tags=rebuild_tags,
        total_reward=total_reward,
        generated_at=datetime.now(),
    )
