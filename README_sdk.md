---
title: Code Profiler Environment
emoji: ⚡
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
dockerfile: Dockerfile
tags:
  - openenv
  - code-profiling
  - performance-optimization
  - reinforcement-learning
  - rl-environment
model_index:
  - name: code-profiler
    results: []
---

# Code Profiler Environment

An OpenEnv RL environment for iterative code profiling and performance optimization. Agents learn to identify and fix performance bottlenecks based on pcode profiler runs. To start with support is available for Python, Java, and C++ code.

## Overview

This environment simulates real-world code profiling tasks where agents must:

1. **Build** code in Python, Java, or C++
2. **Profile** the code to identify performance hotspots
3. **Fix** identified issues
4. **Measure** improvement with graded rewards

## Tasks

### Easy: String Concatenation (Python)
**Task ID:** `python-string-concat-easy`

Fix string concatenation in loops causing slow responses. Optimize the `build_catalog_response` function to use efficient string building.

**Grading:** Normalized score (0.0-1.0) based on execution time improvement.

### Medium: Linear Search (Python)
**Task ID:** `python-linear-search-medium`

Optimize O(n) linear search to O(1) hash lookup for product search. Improve the `find_product_by_id_linear` function.

**Grading:** Normalized score (0.0-1.0) based on execution time and hotspot reduction.

### Hard: Memory Optimization (C++)
**Task ID:** `cpp-memory-optimization-hard`

Optimize C++ implementation with memory allocation issues and excessive copies. Improve cache locality and reduce memory churn.

**Grading:** Normalized score (0.0-1.0) based on execution time, memory usage, and hotspot reduction.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment for a task |
| `/step` | POST | Take an action (build/profile/fix/submit) |
| `/state` | GET | Get current environment state |
| `/tasks` | GET | List all available tasks |
| `/tasks/{id}` | GET | Get specific task details |
| `/health` | GET | Health check |

## Quick Start

### Reset Environment
```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "python-string-concat-easy", "language": "python"}'
```

### Take a Step
```bash
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "build",
    "language": "python",
    "iteration": 0
  }'
```

### Run with Python Client
```python
import asyncio
from environments.code_profiler_env import CodeProfilerEnv, ProfileAction

async def main():
    async with CodeProfilerEnv(base_url="http://localhost:8000") as client:
        result = await client.reset(task_id="python-string-concat-easy")
        print(f"Task: {result.observation.task.name}")

        action = ProfileAction(
            action_type="build",
            language="python",
            iteration=0
        )
        result = await client.step(action)
        print(f"Score: {result.observation.cumulative_score}")

asyncio.run(main())
```

## Action Types

- `build` - Build the code
- `profile` - Run profiler and measure performance
- `fix` - Apply a code fix (include description in `code_fix` field)
- `submit` - Submit the solution

## Reward System

Rewards are normalized scores (0.0-1.0) based on:
- Execution time improvement vs baseline
- Memory usage reduction
- Hotspot percentage reduction
- Iteration efficiency bonus

## Flow
Local Loop (5-7 iterations of improvements or degradation in performance):
  ├── reset() → HF Space
  ├── For each iteration:
  │   ├── LLM analyzes hotspots → HF Router
  │   ├── Apply fix locally
  │   ├── commit git
  │   ├── Docker rebuild (if performance improves)
  │   ├── profile() → measure
  │   └── calculate delta reward
  └── Generate report locally
## Stop Conditions (5-7 iterations):

  Stop at iteration 5 if net_positive achieved
  Up to 2 extensions if iteration 5 is degrade
  Always stop after iteration 7

## License

MIT
