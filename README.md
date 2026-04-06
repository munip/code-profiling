# Code Profiler Environment

An OpenEnv environment for iterative code profiling and performance optimization using RL.

## Overview

This project implements a reinforcement learning environment for code profiling, where an agent can:

1. **Build** code in Python, Java, or C++
2. **Profile** the code to identify performance hotspots
3. **Fix** identified issues
4. **Measure** improvement/degradation with graded rewards

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    opencode Agent                            │
│              (Generates and fixes code)                      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                OpenEnv RL Framework                          │
│         CodeProfilerEnv(reset, step, state)                  │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Python Docker  │ │   Java Docker    │ │    C++ Docker   │
│  (Austin)       │ │ (async-profiler) │ │    (Austin)     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Profiling Tools

| Language | Profiler | Purpose |
|----------|----------|---------|
| Python | Austin | Frame stack sampling |
| Java | async-profiler | CPU/memory profiling |
| C++ | Austin | Frame stack sampling |

## Reward System

Rewards are calculated based on **graded percentage improvement/degradation**:

| Scenario | Change | Reward |
|----------|--------|--------|
| 50% faster | 100ms → 50ms | +2.5 |
| 20% faster | 100ms → 80ms | +1.0 |
| 10% faster | 100ms → 90ms | +0.5 |
| No change | 100ms → 100ms | 0.0 |
| 10% slower | 100ms → 110ms | -0.5 |
| 20% slower | 100ms → 120ms | -1.0 |

Scale: 0.5 per 10% change, capped at ±2.0

## Quick Start

### Installation

```bash
pip install -e .
```

### Run MVP Demo

```bash
python mvp_runner.py
```

### Start Environment Server

```bash
cd environments/code_profiler_env/server
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Use with opencode

```python
from environments.code_profiler_env import CodeProfilerEnv, ProfileAction

with CodeProfilerEnv(base_url="http://localhost:8000") as client:
    result = client.reset()
    
    action = ProfileAction(
        action_type="build",
        language="python",
        iteration=0
    )
    result = client.step(action)
```

## Project Structure

```
code-profiling/
├── environments/
│   └── code_profiler_env/
│       ├── models.py              # Type-safe models
│       ├── client.py              # OpenEnv client
│       └── server/
│           ├── app.py             # FastAPI server
│           ├── code_profiler_environment.py  # Environment logic
│           ├── python/src/app.py  # Python e-commerce API
│           ├── java/src/...       # Java e-commerce API
│           └── cpp/src/main.cpp   # C++ e-commerce API
├── src/
│   ├── profiler_runner.py         # Profiler orchestration
│   ├── hotspot_analyzer.py        # Parse profiler output
│   └── reward_calculator.py       # Performance rewards
├── profiles/                       # Profiler output storage
├── logs/                          # Execution logs
└── mvp_runner.py                  # MVP demonstration
```

## Environment API

### Actions

```python
ProfileAction(
    action_type: Literal["build", "profile", "fix", "test"]
    language: Literal["python", "java", "cpp"]
    iteration: int  # 0-4
    code_fix: Optional[str]  # For fix action
    test_input: Optional[str]  # For profile action
)
```

### Observations

```python
ProfileObservation(
    build_status: bool
    profiler_output: Optional[str]
    hotspots: List[Hotspot]
    execution_time_ms: float
    reward: float  # Graded % improvement
    delta_percent: float
    done: bool
    current_iteration: int
    language: str
    message: str
)
```

## Intentional Performance Issues

The e-commerce APIs contain deliberate anti-patterns for demonstration:

| Language | Issue | Location |
|----------|-------|----------|
| Python | String concatenation in loop | `build_catalog_response()` |
| Python | O(n) linear search | `find_product_by_id_linear()` |
| Java | String concatenation | `buildCatalogResponse()` |
| Java | Linear list search | `findProductLinear()` |
| C++ | Excessive string copies | `build_catalog_response()` |
| C++ | Vector linear search | `find_product_linear()` |

## Docker Deployment

```bash
cd environments/code_profiler_env/server
docker-compose up --build
```

## License

MIT
