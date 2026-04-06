"""Reward calculation based on graded percentage improvement."""

from typing import Optional


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
        """
        Initialize calculator with baseline performance.

        Args:
            baseline_ms: Initial baseline execution time in milliseconds
        """
        self.baseline_ms = baseline_ms
        self.previous_ms = baseline_ms
        self.best_ms = baseline_ms

    def compute_reward(
        self, current_ms: float, previous_ms: Optional[float] = None
    ) -> tuple[float, float]:
        """
        Compute reward based on performance change.

        Args:
            current_ms: Current execution time in milliseconds
            previous_ms: Previous execution time (defaults to stored previous)

        Returns:
            Tuple of (reward, delta_percent)
        """
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
