---
title: openenv-stage1
emoji: 📚
colorFrom: pink
colorTo: red
sdk: docker
pinned: false
---

# Code Profiler Environment

An OpenEnv RL environment for iterative code profiling and performance optimization that work with coding agent generated code in the environment. Performance is the first NFR environment preparation. With this model other NFR requirement orchestration like security, privacy checks or even scalability / availability tests can be added. In this environment, agents learn to identify and fix performance bottlenecks in Python, Java, and C++ code through graded rewards.

## Overview

This environment simulates real-world code profiling tasks where AI agents must:

1. **Build** code in Python, Java, or C++
2. **Profile** the code to identify performance hotspots
3. **Fix** identified issues
4. **Measure** improvement with graded rewards (0.0-1.0)

The environment is designed for the OpenEnv hackathon and follows the full OpenEnv specification with typed models, step()/reset()/state() API, and task-based grading.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Agent (LLM)                            │
│              (Generates and fixes code)                      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                OpenEnv RL Framework                          │
│         CodeProfilerEnv(reset, step, state)                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               Code Profiler Environment Server               │
│     - Task Management (Easy/Medium/Hard)                     │
│     - Performance Graders (0.0-1.0 scores)                   │
│     - Hotspot Analysis                                       │
└─────────────────────────────────────────────────────────────┘
```

## Tasks

### Easy: String Concatenation (Python)
| Property | Value |
|----------|-------|
| Task ID | `python-string-concat-easy` |
| Difficulty | Easy |
| Objective | Fix string concatenation in loops causing slow responses |
| Target | `build_catalog_response()` function |
| Max Iterations | 3 |
| Grading | Normalized score based on execution time improvement |

### Medium: Linear Search (Python)
| Property | Value |
|----------|-------|
| Task ID | `python-linear-search-medium` |
| Difficulty | Medium |
| Objective | Optimize O(n) linear search to O(1) hash lookup |
| Target | `find_product_by_id_linear()` function |
| Max Iterations | 4 |
| Grading | Normalized score based on execution time + hotspot reduction |

### Hard: Memory Optimization (C++)
| Property | Value |
|----------|-------|
| Task ID | `cpp-memory-optimization-hard` |
| Difficulty | Hard |
| Objective | Optimize memory allocation and reduce copies |
| Target | Multiple functions in C++ implementation |
| Max Iterations | 5 |
| Grading | Normalized score based on execution time, memory usage, and hotspot reduction |

## Action & Observation Spaces

### Actions

```python
ProfileAction(
    action_type: Literal["build", "profile", "fix", "test", "submit"]
    language: Literal["python", "java", "cpp"]
    iteration: int  # 0-5
    code_fix: Optional[str]  # Description of fix (for fix action)
    reasoning: Optional[str]  # Agent's reasoning
)
```

### Observations

```python
ProfileObservation(
    build_status: bool
    build_output: Optional[str]
    profiler_output: Optional[str]
    hotspots: List[Hotspot]  # Performance hotspots
    execution_time_ms: float  # Current execution time
    memory_usage_mb: float  # Current memory usage
    reward: float  # Step reward (normalized 0.0-1.0)
    cumulative_score: float  # Running task score (0.0-1.0)
    delta_percent: float  # % change from baseline
    done: bool  # Episode complete
    current_iteration: int
    max_iterations: int
    language: str
    task: Optional[Task]  # Current task definition
    message: str  # Human-readable status
    error: Optional[str]  # Error message if any
)
```

### Hotspot Model

```python
Hotspot(
    function_name: str
    file_path: Optional[str]
    line_number: Optional[int]
    self_time_ms: float
    total_time_ms: float
    call_count: int
    percentage: float  # % of total execution time
)
```

## Reward System

Rewards are **normalized scores (0.0-1.0)** based on:

| Metric | Description | Weight |
|--------|-------------|--------|
| Execution Time | Improvement vs baseline | Varies by task |
| Memory Usage | Reduction from baseline | Varies by task |
| Hotspot Reduction | Lower hotspot % = better | Varies by task |
| Iteration Bonus | Extra points for quick solutions | +0.02 per remaining step |

**Passing threshold:** Score ≥ 0.7

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /reset` | Reset environment for a task |
| `POST /step` | Take an action |
| `GET /state` | Get current environment state |
| `GET /tasks` | List all available tasks |
| `GET /tasks/{id}` | Get specific task details |
| `GET /health` | Health check |

## Setup & Installation

### Prerequisites
- Python 3.10+
- pip
- Docker (for containerized deployment)

### Install Dependencies

```bash
pip install -e .
```

### Run Locally

```bash
cd environments/code_profiler_env/server
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
# Build image
docker build -t code-profiler-env .

# Run container
docker run -p 8000:8000 code-profiler-env
```

### Docker Compose

```bash
docker-compose up --build
```

## Usage Examples

### Python Client

```python
import asyncio
from environments.code_profiler_env import CodeProfilerEnv, ProfileAction

async def main():
    async with CodeProfilerEnv(base_url="http://localhost:8000") as client:
        # Reset for a specific task
        result = await client.reset(task_id="python-string-concat-easy")
        print(f"Task: {result.observation.task.name}")
        print(f"Message: {result.observation.message}")

        # Build
        action = ProfileAction(
            action_type="build",
            language="python",
            iteration=0
        )
        result = await client.step(action)

        # Profile
        action = ProfileAction(
            action_type="profile",
            language="python",
            iteration=1
        )
        result = await client.step(action)
        print(f"Score: {result.observation.cumulative_score}")
        print(f"Hotspots: {result.observation.hotspots}")

asyncio.run(main())
```

### curl Commands

```bash
# Reset environment
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "python-string-concat-easy", "language": "python"}'

# Build
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "build", "language": "python", "iteration": 0}'

# Profile
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "profile", "language": "python", "iteration": 1}'

# Apply fix
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "fix", "language": "python", "iteration": 1, "code_fix": "Use join() instead of +"}'
```

## Inference Script

Run the baseline inference script to evaluate agent performance:

```bash
# Set environment variables
export HF_TOKEN="your-hf-token"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export ENV_BASE_URL="http://localhost:8000"

# Run inference
python inference.py
```

### Output Format

```
[START] task=python-string-concat-easy env=code-profiler model=Qwen2.5-72B
[STEP]  step=1 action=build(language='python') reward=0.00 done=false error=null
[STEP]  step=2 action=profile(language='python') reward=0.65 done=false error=null
[STEP]  step=3 action=fix(code_fix='Use join()...') reward=0.85 done=true error=null
[END]   success=true steps=3 score=0.85 rewards=0.00,0.65,0.85
```

## Baseline Scores

Expected baseline performance on each task:

| Task | Difficulty | Baseline Score | Expected Score |
|------|------------|----------------|----------------|
| String Concatenation | Easy | 0.40 | 0.65-0.85 |
| Linear Search | Medium | 0.35 | 0.55-0.75 |
| Memory Optimization | Hard | 0.25 | 0.40-0.60 |

## Hugging Face Spaces

The environment is deployed as a HuggingFace Space:

```
https://huggingface.co/spaces/<your-org>/code-profiler-env
```

See [README_sdk.md](README_sdk.md) for HF Space configuration details.

## Validation

Run the submission validation script:

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/scripts/validate-submission.sh | bash -s -- <ping_url> [repo_dir]
```

Or locally:

```bash
chmod +x scripts/validate-submission.sh
./scripts/validate-submission.sh https://your-space.hf.space .
```

## Project Structure

```
code-profiling/
├── environments/
│   └── code_profiler_env/
│       ├── __init__.py          # Package exports
│       ├── models.py             # Typed Pydantic models
│       ├── client.py             # OpenEnv client
│       ├── openenv.yaml          # OpenEnv spec
│       └── server/
│           └── app.py            # FastAPI server
|   └── server/                   #Simulated environment for code profiling
|       └──cpp
|          └──src
|          |  └── main.cpp        # Baseline generated C++ code
|          ├──CMAkeLists.txt      # build list for make
|          ├──Dockerfile          # C++ container builder Dockerfile
|       └──java
|          └──src\com\ecommerce\api
|          |  └── ECommerceAPI.java     # Baseline generated Java code
|          ├──Dockerfile          # Java container builder Dockerfile
|       └──python
|          └──src
|          |  └── app.py          # Baseline generated Python code
|          ├──Dockerfile          # Python container builder 
|       ├──app.py                 # Main openenv driver app code
|       ├──Dockerfile             # openenv driving container 
├── inference.py                  # Baseline inference script
├── Dockerfile                    # HF Space Dockerfile
├── docker-compose.yml            # Container orchestration
├── README.md                     # This file
├── README_sdk.md                 # HF Space description
├── pyproject.toml                # Python package config
├── .huggingface/
│   └── config.json              # HF Space metadata
└── scripts/
    └── validate-submission.sh   # Validation script
```

## License

MIT
