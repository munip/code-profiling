"""OpenEnv client for Code Profiler Environment."""

from typing import Optional, List
from openenv.core import EnvClient

from .models import (
    ProfileAction,
    ProfileObservation,
    ProfileState,
    StepResult,
    Task,
    ResetResponse,
    GraderResult,
)


class CodeProfilerEnv(EnvClient):
    """
    Client for the Code Profiler Environment.

    Connect to a running Code Profiler environment server and interact
    with it using the Gymnasium-style API.

    Example:
        with CodeProfilerEnv(base_url="http://localhost:8000") as client:
            result = await client.reset()
            print(f"Initial state: {result.observation}")

            action = ProfileAction(
                action_type="build",
                language="python",
                iteration=0
            )
            result = await client.step(action)
            print(f"Score: {result.observation.cumulative_score}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        connect_timeout_s: float = 10.0,
        message_timeout_s: float = 60.0,
        **kwargs,
    ):
        super().__init__(
            base_url=base_url,
            connect_timeout_s=connect_timeout_s,
            message_timeout_s=message_timeout_s,
            **kwargs,
        )

    async def reset(self, task_id: Optional[str] = None, language: str = "python") -> ResetResponse:
        """Reset the environment and get initial observation."""
        response = await self._post("/reset", json={"task_id": task_id, "language": language})
        data = response.json()
        return ResetResponse(**data)

    async def step(self, action: ProfileAction) -> StepResult:
        """Take a step in the environment."""
        print(f"Taking step with action from the client: {action}")  # Debug statement to show action being taken
        response = await self._post("/step", json=action.model_dump())
        data = response.json()
        return StepResult(**data)

    async def state(self) -> ProfileState:
        """Get current environment state."""
        response = await self._get("/state")
        return ProfileState(**response.json())

    async def get_tasks(self) -> List[Task]:
        """Get all available tasks."""
        response = await self._get("/tasks")
        return [Task(**t) for t in response.json()]

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task."""
        response = await self._get(f"/tasks/{task_id}")
        data = response.json()
        if "error" in data:
            return None
        return Task(**data)

    async def get_hotspots(self) -> list:
        """Get current hotspots from the last profile run."""
        print("Getting current hotspots from the last profile run")  # Debug statement to confirm hotspots retrieval
        response = await self._get("/hotspots")
        print(f"Received hotspots response: {response.json()}")  # Debug statement to show hotspots response

        return response.json()

    async def get_iteration_results(self) -> list:
        """Get all iteration results."""
        print("Getting all iteration results")  # Debug statement to confirm results retrieval
        response = await self._get("/results")
        print(f"Received iteration results response: {response.json()}")  # Debug statement to show results response
        return response.json()
