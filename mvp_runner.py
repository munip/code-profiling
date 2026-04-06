#!/usr/bin/env python3
"""
MVP Runner for Code Profiler Environment.

This script demonstrates the RL loop for code profiling:
1. Generate/load suboptimal code
2. Profile to find hotspots
3. Fix hotspots
4. Measure improvement
5. Track rewards

The simulation runs 4 iterations per language with:
- 2 degradation scenarios (negative rewards)
- 2 improvement scenarios (positive rewards)
"""

import sys
from dataclasses import dataclass
from typing import List, Dict


class PerformanceRewardCalculator:
    """
    Calculates rewards based on graded percentage improvement/degradation.

    Reward scale:
    - Positive reward for improvement (lower execution time)
    - Negative reward for degradation (higher execution time)
    - Magnitude is proportional to % change (0.5 per 10% change)
    - Capped at ±2.0 to prevent extreme outliers
    """

    def __init__(self, baseline_ms: float):
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def compute_reward(self, current_ms: float, previous_ms: float = None) -> tuple[float, float]:
        if previous_ms is not None:
            self.previous_ms = previous_ms

        if self.previous_ms == 0:
            return 0.0, 0.0

        delta_percent = ((current_ms - self.previous_ms) / self.previous_ms) * 100

        if abs(delta_percent) < 0.5:
            return 0.0, delta_percent

        reward = delta_percent * -0.05
        reward = max(-2.0, min(2.0, reward))

        self.previous_ms = current_ms

        if current_ms < self.best_ms:
            self.best_ms = current_ms

        return round(reward, 3), round(delta_percent, 2)


class MockProfilerResult:
    """Simulated profiler results for MVP demonstration."""

    HOTSPOT_PRESETS = {
        "python": [
            {
                "function": "build_catalog_response",
                "file": "app.py",
                "line": 45,
                "percentage": 35.2,
            },
            {
                "function": "find_product_by_id_linear",
                "file": "app.py",
                "line": 28,
                "percentage": 22.1,
            },
            {"function": "calculate_order_total", "file": "app.py", "line": 55, "percentage": 18.5},
            {"function": "deep_copy_product", "file": "app.py", "line": 75, "percentage": 12.3},
            {
                "function": "filter_products_by_category",
                "file": "app.py",
                "line": 82,
                "percentage": 8.9,
            },
        ],
        "java": [
            {
                "function": "buildCatalogResponse",
                "file": "ECommerceAPI.java",
                "line": 85,
                "percentage": 38.1,
            },
            {
                "function": "findProductLinear",
                "file": "ECommerceAPI.java",
                "line": 45,
                "percentage": 25.3,
            },
            {
                "function": "calculateOrderTotal",
                "file": "ECommerceAPI.java",
                "line": 105,
                "percentage": 19.7,
            },
            {
                "function": "deepCopyProduct",
                "file": "ECommerceAPI.java",
                "line": 120,
                "percentage": 10.2,
            },
            {
                "function": "filterByCategory",
                "file": "ECommerceAPI.java",
                "line": 130,
                "percentage": 6.7,
            },
        ],
        "cpp": [
            {
                "function": "build_catalog_response",
                "file": "main.cpp",
                "line": 55,
                "percentage": 32.8,
            },
            {"function": "find_product_linear", "file": "main.cpp", "line": 35, "percentage": 28.4},
            {
                "function": "calculate_order_total",
                "file": "main.cpp",
                "line": 75,
                "percentage": 20.1,
            },
            {"function": "deep_copy_product", "file": "main.cpp", "line": 90, "percentage": 11.5},
            {"function": "format_product_json", "file": "main.cpp", "line": 100, "percentage": 7.2},
        ],
    }

    BASELINE_TIMES = {
        "python": 125.5,
        "java": 98.3,
        "cpp": 82.7,
    }

    ITERATION_SCENARIOS = {
        "python": [
            {"delta": 1.15, "desc": "degraded"},  # 15% slower - degradation
            {"delta": 0.82, "desc": "improved"},  # 18% faster - improvement
            {"delta": 1.08, "desc": "degraded"},  # 8% slower - degradation
            {"delta": 0.75, "desc": "improved"},  # 25% faster - improvement
        ],
        "java": [
            {"delta": 1.12, "desc": "degraded"},  # 12% slower - degradation
            {"delta": 0.85, "desc": "improved"},  # 15% faster - improvement
            {"delta": 1.05, "desc": "degraded"},  # 5% slower - degradation
            {"delta": 0.72, "desc": "improved"},  # 28% faster - improvement
        ],
        "cpp": [
            {"delta": 1.18, "desc": "degraded"},  # 18% slower - degradation
            {"delta": 0.80, "desc": "improved"},  # 20% faster - improvement
            {"delta": 1.10, "desc": "degraded"},  # 10% slower - degradation
            {"delta": 0.68, "desc": "improved"},  # 32% faster - improvement
        ],
    }

    @classmethod
    def get_result(cls, language: str, iteration: int) -> tuple[float, List[Dict], Dict]:
        baseline = cls.BASELINE_TIMES[language]
        scenarios = cls.ITERATION_SCENARIOS[language]

        if iteration == 0:
            execution_time = baseline
            scenario = None
        else:
            scenario = scenarios[iteration - 1]
            execution_time = baseline * scenario["delta"]

        hotspots = cls.HOTSPOT_PRESETS[language]
        return execution_time, hotspots, scenario


@dataclass
class StepRecord:
    iteration: int
    language: str
    action_type: str
    execution_time_ms: float
    delta_percent: float
    reward: float
    hotspots: List[Dict]
    message: str


class MVPRunner:
    """
    MVP Runner that simulates the RL loop for code profiling.

    This demonstrates:
    - 4 iterations per language
    - 2 degradation scenarios (negative rewards)
    - 2 improvement scenarios (positive rewards)
    - Progress tracking and final reporting
    """

    def __init__(self):
        self.languages = ["python", "java", "cpp"]
        self.max_iterations = 4
        self.records: Dict[str, List[StepRecord]] = {lang: [] for lang in self.languages}

    def run_episode(self, language: str) -> List[StepRecord]:
        """Run a complete profiling episode for one language."""
        print(f"\n{'=' * 70}")
        print(f"  Starting Episode for {language.upper()}")
        print(f"{'=' * 70}")

        calculator = PerformanceRewardCalculator(MockProfilerResult.BASELINE_TIMES[language])
        records = []

        for iteration in range(self.max_iterations + 1):
            print(f"\n--- Iteration {iteration} ---")

            execution_time, hotspots, scenario = MockProfilerResult.get_result(language, iteration)

            if iteration == 0:
                reward = 0.0
                delta_percent = 0.0
                message = "Baseline profiling - no comparison"
            else:
                reward, delta_percent = calculator.compute_reward(execution_time)
                scenario_info = f"({scenario['desc']})" if scenario else ""
                if reward > 0:
                    message = f"IMPROVED by {abs(delta_percent):.1f}%! {scenario_info}"
                elif reward < 0:
                    message = f"DEGRADED by {abs(delta_percent):.1f}%. {scenario_info}"
                else:
                    message = "No significant change."

            record = StepRecord(
                iteration=iteration,
                language=language,
                action_type="profile",
                execution_time_ms=execution_time,
                delta_percent=delta_percent,
                reward=reward,
                hotspots=hotspots[:3],
                message=message,
            )
            records.append(record)

            print(f"  Execution Time: {execution_time:.2f}ms")
            print(f"  Delta: {delta_percent:+.2f}%")
            print(f"  Reward: {reward:+.3f}")
            print(f"  Status: {message}")
            print(f"  Top Hotspot: {hotspots[0]['function']} ({hotspots[0]['percentage']:.1f}%)")

        return records

    def run_all_episodes(self):
        """Run episodes for all languages."""
        print("\n" + "=" * 70)
        print("  CODE PROFILER ENVIRONMENT - MVP DEMONSTRATION")
        print("=" * 70)
        print(f"\nLanguages: {', '.join(self.languages)}")
        print(f"Iterations per language: {self.max_iterations}")
        print(f"Reward scale: graded % improvement/degradation (0.5 per 10%)")

        for language in self.languages:
            records = self.run_episode(language)
            self.records[language] = records

        self.print_summary()

    def print_summary(self):
        """Print summary table of all results."""
        print("\n" + "=" * 70)
        print("  SUMMARY TABLE")
        print("=" * 70)

        header = f"| {'Language':<10} | {'Iter':<5} | {'Exec(ms)':<10} | {'Delta%':<8} | {'Reward':<8} | {'Status':<20} |"
        sep = "-" * 76

        print(f"\n{header}")
        print(f"|{'-' * 12}|{'-' * 7}|{'-' * 12}|{'-' * 10}|{'-' * 10}|{'-' * 22}|")

        for language in self.languages:
            records = self.records[language]
            for i, record in enumerate(records):
                if record.reward > 0:
                    status = "IMPROVED"
                elif record.reward < 0:
                    status = "DEGRADED"
                else:
                    status = "BASELINE" if record.iteration == 0 else "NO CHANGE"

                print(
                    f"| {record.language:<10} | {record.iteration:<5} | {record.execution_time_ms:<10.2f} | {record.delta_percent:<+8.2f} | {record.reward:<+8.3f} | {status:<20} |"
                )

            print(f"|{'-' * 12}|{'-' * 7}|{'-' * 12}|{'-' * 10}|{'-' * 10}|{'-' * 22}|")

        self.print_final_outcomes()

    def print_final_outcomes(self):
        """Print final outcomes per language."""
        print("\n" + "=" * 70)
        print("  FINAL OUTCOMES")
        print("=" * 70)

        print(
            f"\n{'Language':<12} | {'Baseline':<12} | {'Final':<12} | {'Improvement':<15} | {'Total Reward':<12}"
        )
        print("-" * 75)

        for language in self.languages:
            records = self.records[language]
            baseline = records[0].execution_time_ms
            final = records[-1].execution_time_ms
            improvement = ((baseline - final) / baseline) * 100
            total_reward = sum(r.reward for r in records)

            print(
                f"{language:<12} | {baseline:<12.2f} | {final:<12.2f} | {improvement:<+15.2f}% | {total_reward:<+12.3f}"
            )

        print("\n" + "-" * 75)
        print("\nReward Legend:")
        print("  - Positive reward = Performance improved (faster)")
        print("  - Negative reward = Performance degraded (slower)")
        print("  - Magnitude: 0.5 per 10% change (capped at +-2.0)")
        print("\n" + "=" * 70)
        print("  MVP DEMONSTRATION COMPLETE")
        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    runner = MVPRunner()
    runner.run_all_episodes()


if __name__ == "__main__":
    main()
