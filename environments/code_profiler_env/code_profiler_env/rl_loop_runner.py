#!/usr/bin/env python3
"""
RL Loop Integration for Code Profiler Environment with opencode.

This script demonstrates the full reinforcement learning loop:
1. Reset environment with suboptimal code
2. Profile to identify hotspots
3. Generate fix using opencode-style prompts
4. Apply fix and re-profile
5. Calculate reward based on performance improvement

Usage:
    python rl_loop_runner.py [--language python|java|cpp] [--iterations N]
"""

import argparse
import json
import httpx
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys


@dataclass
class Hotspot:
    function_name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    self_time_ms: float = 0.0
    total_time_ms: float = 0.0
    call_count: int = 0
    percentage: float = 0.0


@dataclass
class IterationResult:
    iteration: int
    action_type: str
    hotspots: List[Hotspot] = field(default_factory=list)
    execution_time_ms: float = 0.0
    reward: float = 0.0
    delta_percent: float = 0.0
    fix_applied: Optional[str] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class CodeProfilerClient:
    """Client for Code Profiler Environment API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def reset(self, language: str = "python") -> Dict[str, Any]:
        """Reset the environment."""
        response = self.client.post(f"{self.base_url}/reset", json={"language": language})
        response.raise_for_status()
        return response.json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a step."""
        response = self.client.post(f"{self.base_url}/step", json=action)
        response.raise_for_status()
        return response.json()

    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        response = self.client.get(f"{self.base_url}/state")
        response.raise_for_status()
        return response.json()

    def get_hotspots(self) -> List[Dict[str, Any]]:
        """Get current hotspots."""
        response = self.client.get(f"{self.base_url}/hotspots")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the client."""
        self.client.close()


class PerformanceFixGenerator:
    """Generates performance fixes based on hotspots (simulates opencode agent)."""

    FIX_TEMPLATES = {
        "python": {
            "string_concat": """
# Fix: Replace string concatenation with join
def build_catalog_response():
    parts = []
    for product in PRODUCTS_DB:
        parts.append(f"ID: {product['id']}, Name: {product['name']}, Price: ${product['price']}")
    return " | ".join(parts)
""",
            "linear_search": """
# Fix: Use dict for O(1) lookup instead of linear search
PRODUCTS_BY_ID = {p['id']: p for p in PRODUCTS_DB}

def find_product_by_id(product_id: str):
    return PRODUCTS_BY_ID.get(product_id)
""",
            "deep_copy": """
# Fix: Return reference instead of deep copy
def get_product(product_id: str):
    return PRODUCTS_BY_ID.get(product_id)
""",
        },
        "java": {
            "string_concat": """
// Fix: Use StringBuilder instead of concatenation
static String buildCatalogResponse() {
    StringBuilder sb = new StringBuilder();
    for (Product p : productsDb) {
        sb.append("{")
        .append("\"id\":\"").append(p.id).append("\",")
        .append("\"name\":\"").append(p.name).append("\",")
        .append("\"price\":").append(p.price).append("}")
        .append(",");
    }
    return "[" + sb.toString() + "{}]";
}
""",
            "linear_search": """
// Fix: Use HashMap for O(1) lookup
static Map<String, Product> productsById = new HashMap<>();
static {
    for (Product p : productsDb) productsById.put(p.id, p);
}

static Product findProduct(String productId) {
    return productsById.get(productId);
}
""",
        },
        "cpp": {
            "string_concat": """
// Fix: Use string stream or reserve for string building
string build_catalog_response() {
    ostringstream oss;
    for (const auto& product : products_db) {
        oss << "ID: " << product.id << ", "
           << "Name: " << product.name << ", "
           << "Price: $" << product.price << " | ";
    }
    return oss.str();
}
""",
            "linear_search": """
// Fix: Use unordered_map for O(1) lookup
unordered_map<string, Product*> products_by_id;

void init_product_map() {
    for (auto& p : products_db) {
        products_by_id[p.id] = &p;
    }
}

Product* find_product(const string& id) {
    auto it = products_by_id.find(id);
    return (it != products_by_id.end()) ? it->second : nullptr;
}
""",
        },
    }

    @classmethod
    def generate_fix(cls, language: str, hotspots: List[Hotspot]) -> str:
        """Generate a fix based on identified hotspots."""
        if not hotspots:
            return "# No hotspots identified"

        fixes = []
        for hotspot in hotspots[:2]:
            func_name = hotspot.function_name.lower()

            if "concat" in func_name or "build" in func_name:
                fix_type = "string_concat"
            elif "linear" in func_name or "find" in func_name:
                fix_type = "linear_search"
            elif "copy" in func_name:
                fix_type = "deep_copy"
            else:
                continue

            if fix_type in cls.FIX_TEMPLATES.get(language, {}):
                fixes.append(cls.FIX_TEMPLATES[language][fix_type])

        return "\n\n".join(fixes) if fixes else "# No specific fix available"


class PerformanceRewardCalculator:
    """Calculates rewards based on graded percentage improvement."""

    def __init__(self, baseline_ms: float):
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def compute_reward(self, current_ms: float) -> tuple[float, float]:
        """Compute reward based on performance change."""
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


class RLLoopRunner:
    """
    Runs the RL loop for code profiling.

    This demonstrates:
    1. Environment reset with suboptimal code
    2. Profiling to identify hotspots
    3. Generating fixes (simulating opencode)
    4. Applying fixes and re-profiling
    5. Calculating rewards based on improvement
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        language: str = "python",
        max_iterations: int = 4,
    ):
        self.client = CodeProfilerClient(base_url)
        self.fix_generator = PerformanceFixGenerator()
        self.language = language
        self.max_iterations = max_iterations
        self.calculator: Optional[PerformanceRewardCalculator] = None
        self.results: List[IterationResult] = []
        self.baseline_time = 0.0

    def run_episode(self) -> List[IterationResult]:
        """Run a complete episode."""
        print(f"\n{'=' * 70}")
        print(f"  Starting RL Episode for {self.language.upper()}")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"{'=' * 70}")

        self.client.reset(self.language)

        for iteration in range(self.max_iterations + 1):
            self.run_iteration(iteration)

        self.print_summary()
        return self.results

    def run_iteration(self, iteration: int):
        """Run a single iteration."""
        print(f"\n--- Iteration {iteration} ---")

        if iteration == 0:
            self.run_baseline()
        else:
            self.run_fix_iteration(iteration)

    def run_baseline(self):
        """Run baseline profiling."""
        print("  Running baseline profile...")

        build_result = self.client.step(
            {"action_type": "build", "language": self.language, "iteration": 0}
        )

        obs = build_result["observation"]
        print(f"  Build status: {'SUCCESS' if obs['build_status'] else 'FAILED'}")

        profile_result = self.client.step(
            {"action_type": "profile", "language": self.language, "iteration": 0}
        )

        obs = profile_result["observation"]
        execution_time = obs["execution_time_ms"]
        self.baseline_time = execution_time
        self.calculator = PerformanceRewardCalculator(execution_time)

        hotspots = [Hotspot(**h) for h in obs.get("hotspots", [])]

        print(f"  Execution time: {execution_time:.2f}ms")
        print(f"  Top hotspot: {hotspots[0].function_name if hotspots else 'None'}")

        result = IterationResult(
            iteration=0,
            action_type="profile",
            hotspots=hotspots,
            execution_time_ms=execution_time,
            reward=0.0,
            delta_percent=0.0,
            message=f"Baseline: {execution_time:.2f}ms",
        )
        self.results.append(result)

    def run_fix_iteration(self, iteration: int):
        """Run an iteration with a fix."""
        prev_hotspots = self.results[-1].hotspots if self.results else []

        print(f"  Analyzing hotspots from iteration {iteration - 1}...")
        fix_code = self.fix_generator.generate_fix(self.language, prev_hotspots)

        print(f"  Applying fix...")
        fix_result = self.client.step(
            {
                "action_type": "fix",
                "language": self.language,
                "iteration": iteration,
                "code_fix": fix_code,
            }
        )

        print(f"  Re-profiling...")
        profile_result = self.client.step(
            {"action_type": "profile", "language": self.language, "iteration": iteration}
        )

        obs = profile_result["observation"]
        execution_time = obs["execution_time_ms"]
        reward, delta = self.calculator.compute_reward(execution_time)

        hotspots = [Hotspot(**h) for h in obs.get("hotspots", [])]

        status = "IMPROVED" if reward > 0 else "DEGRADED" if reward < 0 else "NO CHANGE"
        print(f"  Execution time: {execution_time:.2f}ms (delta: {delta:+.2f}%)")
        print(f"  Reward: {reward:+.3f} [{status}]")
        print(f"  Top hotspot: {hotspots[0].function_name if hotspots else 'None'}")

        result = IterationResult(
            iteration=iteration,
            action_type="fix",
            hotspots=hotspots,
            execution_time_ms=execution_time,
            reward=reward,
            delta_percent=delta,
            fix_applied=fix_code[:200] + "..." if len(fix_code) > 200 else fix_code,
            message=f"{status}: {execution_time:.2f}ms (reward: {reward:+.3f})",
        )
        self.results.append(result)

    def print_summary(self):
        """Print summary of the episode."""
        print(f"\n{'=' * 70}")
        print(f"  EPISODE SUMMARY - {self.language.upper()}")
        print(f"{'=' * 70}")

        header = (
            f"| {'Iter':<5} | {'Time(ms)':<12} | {'Delta%':<10} | {'Reward':<10} | {'Status':<15} |"
        )
        sep = f"|{'-' * 7}|{'-' * 14}|{'-' * 12}|{'-' * 12}|{'-' * 17}|"

        print(f"\n{header}")
        print(sep)

        for r in self.results:
            if r.reward > 0:
                status = "IMPROVED"
            elif r.reward < 0:
                status = "DEGRADED"
            else:
                status = "BASELINE"

            print(
                f"| {r.iteration:<5} | {r.execution_time_ms:<12.2f} | {r.delta_percent:<+10.2f} | {r.reward:<+10.3f} | {status:<15} |"
            )

        print(sep)

        if self.results:
            baseline = self.results[0].execution_time_ms
            final = self.results[-1].execution_time_ms
            total_reward = sum(r.reward for r in self.results)
            improvement = ((baseline - final) / baseline * 100) if baseline > 0 else 0

            print(f"\n  Baseline: {baseline:.2f}ms")
            print(f"  Final: {final:.2f}ms")
            print(f"  Improvement: {improvement:+.2f}%")
            print(f"  Total Reward: {total_reward:+.3f}")

            if total_reward > 0:
                print(f"\n  SUCCESS: Agent achieved net positive improvement!")
            else:
                print(f"\n  RESULT: Agent did not achieve net positive improvement.")

        print(f"\n{'=' * 70}\n")


class OpenCodeIntegration:
    """
    Integration layer for opencode agent.

    This class provides the interface that an opencode agent would use
    to interact with the code profiler environment.
    """

    def __init__(self, workspace_path: str = ".", base_url: str = "http://localhost:8000"):
        self.workspace_path = workspace_path
        self.client = CodeProfilerClient(base_url)
        self.runner = None

    async def run_task(self, task: str, language: str = "python") -> Dict[str, Any]:
        """
        Run a profiling task with opencode.

        This simulates what opencode would do:
        1. Generate/load code
        2. Build and profile
        3. Identify hotspots
        4. Generate fixes
        5. Measure improvement
        """
        print(f"\n{'=' * 70}")
        print(f"  OPENCODE TASK: {task}")
        print(f"  Language: {language}")
        print(f"{'=' * 70}")

        self.runner = RLLoopRunner(
            base_url=self.client.base_url, language=language, max_iterations=4
        )

        results = self.runner.run_episode()

        return {
            "task": task,
            "language": language,
            "results": [
                {
                    "iteration": r.iteration,
                    "execution_time_ms": r.execution_time_ms,
                    "reward": r.reward,
                    "delta_percent": r.delta_percent,
                    "hotspots": [
                        {"function": h.function_name, "percentage": h.percentage}
                        for h in r.hotspots
                    ],
                    "message": r.message,
                }
                for r in results
            ],
            "summary": {
                "baseline_ms": results[0].execution_time_ms if results else 0,
                "final_ms": results[-1].execution_time_ms if results else 0,
                "total_reward": sum(r.reward for r in results),
                "improvement_percent": (
                    (
                        (results[0].execution_time_ms - results[-1].execution_time_ms)
                        / results[0].execution_time_ms
                        * 100
                    )
                    if results and results[0].execution_time_ms > 0
                    else 0
                ),
            },
        }

    def close(self):
        """Close all connections."""
        if self.client:
            self.client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RL Loop Runner for Code Profiler Environment")
    parser.add_argument(
        "--language",
        "-l",
        choices=["python", "java", "cpp"],
        default="python",
        help="Programming language to profile",
    )
    parser.add_argument(
        "--iterations", "-i", type=int, default=4, help="Number of iterations (default: 4)"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8000", help="Base URL of the profiler environment"
    )
    parser.add_argument(
        "--all-languages", action="store_true", help="Run for all languages (python, java, cpp)"
    )

    args = parser.parse_args()

    if args.all_languages:
        languages = ["python", "java", "cpp"]
    else:
        languages = [args.language]

    all_results = []

    for lang in languages:
        runner = RLLoopRunner(base_url=args.base_url, language=lang, max_iterations=args.iterations)
        results = runner.run_episode()
        all_results.append((lang, results))

    print(f"\n{'=' * 70}")
    print(f"  FINAL COMPARISON TABLE")
    print(f"{'=' * 70}")

    print(
        f"\n| {'Language':<10} | {'Baseline':<12} | {'Final':<12} | {'Improvement':<15} | {'Reward':<10} |"
    )
    print(f"|{'-' * 12}|{'-' * 14}|{'-' * 14}|{'-' * 17}|{'-' * 12}|")

    for lang, results in all_results:
        if results:
            baseline = results[0].execution_time_ms
            final = results[-1].execution_time_ms
            improvement = ((baseline - final) / baseline * 100) if baseline > 0 else 0
            total_reward = sum(r.reward for r in results)

            print(
                f"| {lang:<10} | {baseline:<12.2f} | {final:<12.2f} | {improvement:<+15.2f}% | {total_reward:<+10.3f} |"
            )

    print(f"\n{'=' * 70}")
    print(f"  RUN COMPLETE")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
