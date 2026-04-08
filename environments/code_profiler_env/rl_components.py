"""
RL Components for Code Profiler Environment.

Reusable components for the multi-iteration RL loop including:
- GitManager: Git operations for code versioning
- CodeFixer: Apply baseline/optimized/degraded code
- ContainerManager: Docker container rebuilds
- PerformanceRewardCalculator: Reward calculation
"""

import subprocess
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path


BASELINE_COMMIT = "baseline"
LANGUAGE_PORTS = {"python": 8100, "java": 8200, "cpp": 8300}


@dataclass
class IterationResult:
    """Result from a single iteration."""

    iteration: int
    outcome: str = ""
    execution_time_ms: float = 0.0
    reward: float = 0.0
    delta_percent: float = 0.0
    status: str = ""
    message: str = ""
    rebuilt: bool = False
    tag: str = ""


class GitManager:
    """Handles git operations for code versioning."""

    def __init__(self, repo_path: Path = None):
        self.repo_path = repo_path or Path.cwd()

    def commit(self, message: str) -> str:
        """Commit current changes."""
        try:
            subprocess.run(
                ["git", "add", "-A"], cwd=self.repo_path, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.repo_path, capture_output=True, text=True
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def commit_performance_fix(
        self, iteration: int, result: str, issue_type: str = None, diff_summary: str = None
    ) -> str:
        """
        Commit with performance iteration message format.

        Args:
            iteration: The iteration number
            result: 'improve', 'degrade', or 'remove(previous optimized change)'
            issue_type: The type of issue fixed (e.g., 'string_concat', 'linear_search')
            diff_summary: Optional summary of the code changes

        Returns:
            The commit SHA if successful, empty string otherwise
        """
        issue_tag = f"({issue_type})" if issue_type else ""
        message = f"iteration {iteration}: {result} {issue_tag}"

        if diff_summary:
            message = f"{message}\n\n{diff_summary}"

        return self.commit(message)

    def is_repo_clean(self) -> bool:
        """Check if the repository has uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True
            )
            return len(result.stdout.strip()) == 0
        except Exception:
            return True

    def get_diff_summary(self, file_path: str = None) -> str:
        """Get a summary of changes."""
        try:
            cmd = ["git", "diff", "--stat"]
            if file_path:
                cmd.append("--", file_path)

            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def checkout_from_baseline(self, path: str) -> bool:
        """Checkout a file from the baseline commit."""
        try:
            result = subprocess.run(
                ["git", "checkout", BASELINE_COMMIT, "--", path],
                cwd=self.repo_path,
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def checkout_file_from_sha(self, sha: str, path: str) -> bool:
        """Checkout a file from a specific commit SHA."""
        try:
            result = subprocess.run(
                ["git", "checkout", sha, "--", path], cwd=self.repo_path, capture_output=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_file_at_commit(self, file_path: Path, commit: str = BASELINE_COMMIT) -> str:
        """Get file content at a specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit}:{file_path}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    def get_current_sha(self) -> str:
        """Get current commit SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.repo_path, capture_output=True, text=True
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""


class CodeFixer:
    """Applies code fixes to build_catalog_response function."""

    BASELINE_CODE = {
        "python": '''def build_catalog_response() -> str:
    """
    PERFORMANCE ISSUE: Inefficient string building with concatenation.
    Should use list + join() or f-strings.
    """
    response = ""
    for product in PRODUCTS_DB:
        response = response + "ID: " + product["id"] + ", "
        response = response + "Name: " + product["name"] + ", "
        response = response + "Price: $" + str(product["price"]) + " | "
    return response
''',
        "java": """static String buildCatalogResponse() {
        String response = "";
        for (Product p : productsDb) {
            response = response + "{";
            response = response + "\\"id\\":\\"" + p.id + "\\",";
            response = response + "\\"name\\":\\"" + p.name + "\\",";
            response = response + "\\"price\\":" + p.price + ",";
            response = response + "\\"category\\":\\"" + p.category + "\\",";
            response = response + "\\"stock\\":" + p.stock;
            response = response + "},";
        }
        return response;
    }""",
        "cpp": """string build_catalog_response() {
    string response = "";
    for (const auto& product : products_db) {
        response = response + "ID: " + product.id + ", ";
        response = response + "Name: " + product.name + ", ";
        response = response + "Price: $" + to_string(product.price) + " | ";
        response = response + "Category: " + product.category + " || ";
    }
    return response;
}""",
    }

    OPTIMIZED_CODE = {
        "python": '''def build_catalog_response() -> str:
    """
    OPTIMIZED: Efficient string building with list + join.
    """
    parts = []
    for product in PRODUCTS_DB:
        parts.append(f"ID: {product['id']}, Name: {product['name']}, Price: ${product['price']}")
    return " | ".join(parts)
''',
        "java": """static String buildCatalogResponse() {
        StringBuilder sb = new StringBuilder();
        for (Product p : productsDb) {
            if (sb.length() > 0) sb.append(",");
            sb.append("{")
              .append("\\"id\\":\\"").append(p.id).append("\\",")
              .append("\\"name\\":\\"").append(p.name).append("\\",")
              .append("\\"price\\":").append(p.price).append(",")
              .append("\\"category\\":\\"").append(p.category).append("\\",")
              .append("\\"stock\\":").append(p.stock).append("}");
        }
        return "[" + sb.toString() + "{}]";
    }""",
        "cpp": """string build_catalog_response() {
    ostringstream oss;
    for (const auto& product : products_db) {
        if (oss.tellp() > 0) oss << " | ";
        oss << "ID: " << product.id << ", Name: " << product.name
            << ", Price: $" << product.price;
    }
    return oss.str();
}""",
    }

    DEGRADED_CODE = {
        "python": '''def build_catalog_response() -> str:
    """
    DEGRADED: Added wasteful CPU operations.
    """
    for _ in range(5000):
        _ = sum(range(100))
    parts = []
    for product in PRODUCTS_DB:
        parts.append(f"ID: {product['id']}, Name: {product['name']}, Price: ${product['price']}")
    return " | ".join(parts)
''',
        "java": """static String buildCatalogResponse() {
        for (int i = 0; i < 5000; i++) {
            String temp = "";
            for (int j = 0; j < 100; j++) temp += "x";
        }
        StringBuilder sb = new StringBuilder();
        for (Product p : productsDb) {
            if (sb.length() > 0) sb.append(",");
            sb.append("{")
              .append("\\"id\\":\\"").append(p.id).append("\\",")
              .append("\\"name\\":\\"").append(p.name).append("\\",")
              .append("\\"price\\":").append(p.price).append(",")
              .append("\\"category\\":\\"").append(p.category).append("\\",")
              .append("\\"stock\\":").append(p.stock).append("}");
        }
        return "[" + sb.toString() + "{}]";
    }""",
        "cpp": """string build_catalog_response() {
    for (int i = 0; i < 5000; i++) {
        string temp = "";
        for (int j = 0; j < 100; j++) temp += "x";
    }
    ostringstream oss;
    for (const auto& product : products_db) {
        if (oss.tellp() > 0) oss << " | ";
        oss << "ID: " << product.id << ", Name: " << product.name
            << ", Price: $" << product.price;
    }
    return oss.str();
}""",
    }

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path.cwd()
        self.git_manager = GitManager(base_dir)
        self.original_baseline: Dict[str, str] = {}
        self.source_paths: Dict[str, Path] = {}

    def set_source_path(self, language: str, path: Path):
        """Set the source file path for a language."""
        self.source_paths[language] = path

    def read_source(self, language: str) -> str:
        """Read source file for a language."""
        path = self.source_paths.get(language)
        if path and path.exists():
            return path.read_text()
        return ""

    def save_baseline(self, language: str):
        """Save the baseline code for a language."""
        path = self.source_paths.get(language)
        if path:
            content = self.git_manager.get_file_at_commit(path, BASELINE_COMMIT)
            if content:
                self.original_baseline[language] = content

    def find_function_range(self, code: str, func_signature: str, language: str = "java") -> tuple:
        """Find the start and end indices of a function."""
        start = code.find(func_signature)
        if start == -1:
            return -1, -1

        if language == "python":
            lines = code[start:].split("\n")
            func_indent = len(lines[0]) - len(lines[0].lstrip())
            end = start + len(lines[0])

            for i in range(1, len(lines)):
                line = lines[i]
                if line.strip() == "":
                    continue
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= func_indent:
                    end = start + sum(len(l) + 1 for l in lines[:i])
                    break
            else:
                end = len(code)
            return start, end
        else:
            brace_count = 0
            in_func = False
            end = start
            for i in range(start, len(code)):
                if code[i] == "{":
                    brace_count += 1
                    in_func = True
                elif code[i] == "}":
                    brace_count -= 1
                    if in_func and brace_count == 0:
                        end = i + 1
                        break
            return start, end

    def apply_code(self, language: str, new_code: str) -> bool:
        """Apply new code to a language's source file."""
        code = self.read_source(language)
        if not code:
            return False

        if language == "python":
            func_sig = "def build_catalog_response()"
        elif language == "java":
            func_sig = "static String buildCatalogResponse()"
        else:
            func_sig = "string build_catalog_response()"

        start, end = self.find_function_range(code, func_sig, language)
        if start == -1:
            return False

        new_file_code = code[:start] + new_code + code[end:]
        path = self.source_paths.get(language)
        if path:
            path.write_text(new_file_code)
            return True
        return False

    def apply_baseline(self, language: str) -> bool:
        """Apply baseline code."""
        return self.apply_code(language, self.BASELINE_CODE.get(language, ""))

    def apply_optimized(self, language: str) -> bool:
        """Apply optimized code."""
        return self.apply_code(language, self.OPTIMIZED_CODE.get(language, ""))

    def apply_degraded(self, language: str) -> bool:
        """Apply degraded code."""
        return self.apply_code(language, self.DEGRADED_CODE.get(language, ""))


class ContainerManager:
    """Manages Docker container rebuilds.

    Docker operations are handled via CI/CD (GitHub Actions) when code is pushed.
    At runtime, this attempts local rebuilds but gracefully handles unavailability.

    For HF Spaces: Docker builds happen via CI/CD on push to main branch.
    For local development: Docker builds happen directly if docker-compose is available.
    """

    CONTAINERS = {
        "python": "code_profiler_env-python-container-1",
        "java": "code_profiler_env-java-container-1",
        "cpp": "code_profiler_env-cpp-container-1",
    }

    @classmethod
    def rebuild(cls, language: str, version: int, compose_dir: Path = None) -> bool:
        """Rebuild a Docker container for a language.

        For CI/CD: This runs via GitHub Actions on every push.
        For runtime: Attempts local rebuild if Docker is available.

        Returns:
            True if rebuild was successful or CI/CD build is configured.
            False if local Docker is unavailable (HF Spaces).
        """
        if compose_dir is None:
            compose_dir = Path.cwd() / "environments" / "code_profiler_env"

        tag = f"code_profiler_env-{language}-container:v{version}"

        if cls._is_docker_available():
            return cls._rebuild_local(language, version, compose_dir)
        else:
            cls._log_ci_build(language, version, tag)
            return True

    @classmethod
    def _is_docker_available(cls) -> bool:
        """Check if Docker and docker-compose are available."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, timeout=5, check=True)
            subprocess.run(
                ["docker-compose", "--version"], capture_output=True, timeout=5, check=True
            )
            return True
        except Exception:
            return False

    @classmethod
    def _rebuild_local(cls, language: str, version: int, compose_dir: Path) -> bool:
        """Perform local Docker rebuild."""
        container = cls.CONTAINERS.get(language)
        if not container:
            return False

        try:
            subprocess.run(["docker", "stop", container], capture_output=True, timeout=30)
            subprocess.run(["docker", "rm", container], capture_output=True, timeout=30)
        except Exception:
            pass

        result = subprocess.run(
            ["docker-compose", "build", f"{language}-container"],
            cwd=str(compose_dir),
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            return False

        tag = f"code_profiler_env-{language}-container:v{version}"
        subprocess.run(
            ["docker", "tag", f"code_profiler_env-{language}-container:latest", tag],
            capture_output=True,
        )

        subprocess.run(
            ["docker-compose", "up", "-d", f"{language}-container"],
            cwd=str(compose_dir),
            capture_output=True,
        )

        for _ in range(30):
            time.sleep(1)
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip() == "true":
                return True
        return False

    @classmethod
    def _log_ci_build(cls, language: str, version: int, tag: str):
        """Log that CI/CD will handle the build."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"[CI/CD] Docker build delegated to CI. "
            f"Image will be built on next push to main branch. "
            f"Tag: {tag}"
        )


class PerformanceRewardCalculator:
    """Calculates rewards based on graded percentage improvement/degradation."""

    def __init__(self, baseline_ms: float):
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def compute_reward(self, current_ms: float, previous_ms: float = None) -> tuple[float, float]:
        """Compute reward and delta percentage."""
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

    def reset(self, baseline_ms: float):
        """Reset calculator with new baseline."""
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def get_summary(self) -> dict:
        """Get summary of performance history."""
        return {
            "baseline_ms": self.baseline_ms,
            "previous_ms": self.previous_ms,
            "best_ms": self.best_ms,
            "improvement_from_baseline": (
                ((self.baseline_ms - self.best_ms) / self.baseline_ms * 100)
                if self.baseline_ms > 0
                else 0
            ),
        }


class OutcomeDeterminer:
    """Determines iteration outcomes to ensure 2 improvements and 2 degradations."""

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)

    def determine_outcome(self, outcome_history: List[str]) -> str:
        """Determine the next outcome based on history."""
        improvements = sum(1 for o in outcome_history if o == "improve")
        degradations = sum(1 for o in outcome_history if "degrade" in o)

        if improvements < 2 and degradations >= 2:
            return "improve"
        elif degradations < 2 and improvements >= 2:
            return random.choice(["degrade", "remove"])
        elif improvements >= 2 and degradations >= 2:
            return random.choice(["improve", "degrade", "remove"])
        else:
            return random.choice(["improve", "degrade", "remove"])
