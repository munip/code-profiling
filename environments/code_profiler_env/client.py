"""OpenEnv client for Code Profiler Environment."""

from typing import Optional
from openenv import EnvClient

from .models import (
    ProfileAction,
    ProfileObservation,
    ProfileState,
    StepResult,
)


class CodeProfilerEnv(EnvClient):
    """
    Client for the Code Profiler Environment.

    Connect to a running Code Profiler environment server and interact
    with it using the Gymnasium-style API.

    Example:
        with CodeProfilerEnv(base_url="http://localhost:8000") as client:
            result = client.reset()
            print(f"Initial state: {result.observation}")

            action = ProfileAction(
                action_type="build",
                language="python",
                iteration=0
            )
            result = client.step(action)
            print(f"Reward: {result.observation.reward}")
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

    async def reset(self, **kwargs) -> StepResult:
        """Reset the environment and get initial observation."""
        response = await self._post("/reset", json=kwargs)
        data = response.json()

        observation = ProfileObservation(**data["observation"])
        state = ProfileState(**data["state"])

        return StepResult(observation=observation, state=state)

    async def step(self, action: ProfileAction) -> StepResult:
        """Take a step in the environment."""
        response = await self._post("/step", json=action.model_dump())
        data = response.json()

        observation = ProfileObservation(**data["observation"])
        state = ProfileState(**data["state"])

        return StepResult(observation=observation, state=state)

    async def state(self) -> ProfileState:
        """Get current environment state."""
        response = await self._post("/state", json={})
        return ProfileState(**response.json())

    async def get_hotspots(self) -> list:
        """Get current hotspots from the last profile run."""
        response = await self._get("/hotspots")
        return response.json()

    async def get_iteration_results(self) -> list:
        """Get all iteration results."""
        response = await self._get("/results")
        return response.json()
