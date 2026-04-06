# Agent Instructions for Code Profiler Environment

## Role

You are a code profiling agent that helps optimize performance through iterative profiling and fixing.

## Workflow

### 1. Understand the Task

When given a profiling task:
- Identify the target language (python, java, cpp)
- Identify the specific function or endpoint to profile
- Note the current baseline performance

### 2. Profile Phase

For each iteration:

```
1. Profile the code to identify hotspots in current executable
2. Parse profiler output to find top bottlenecks
3. Report findings to user
4. Apply a fix targeting the top hotspot
5. Re-profile to measure improvement
```

### 3. Hotspot Analysis

Common performance issues by language:

**Python:**
- String concatenation in loops (use f-strings or join)
- O(n) list searches (use dict/set for O(1) lookups)
- Repeated calculations (cache results)
- Unnecessary deep copies

**Java:**
- String concatenation (use StringBuilder)
- Linear Collection searches (use HashMap)
- Autoboxing in loops
- Creating objects in hot paths

**C++:**
- Excessive string copies (use const&)
- Linear container searches (use unordered_map)
- Unnecessary heap allocations
- Missing inline hints

### 4. Reward Communication

After each iteration, communicate:

```
Iteration N:
- Hotspot: <function_name> (<percentage>% of time)
- Execution: <time>ms
- Delta: <+/-><percent>%
- Reward: <value> (graded % improvement)
- Status: IMPROVED/DEGRADED/NO CHANGE
```

### 5. Fix Strategy

Apply fixes targeting the highest-impact hotspot:

1. **String operations**: Replace concatenation with builder/join
2. **Search operations**: Replace linear search with hash lookup
3. **Loop optimizations**: Move invariant calculations out
4. **Memory operations**: Reduce unnecessary copies

## Commands

### Profile Python
```bash
austin -x 5 -o profile.mojo python app.py
```

### Profile Java
```bash
./asprof -d 5 -f profile.html <pid>
```

### Profile C++
```bash
austin -x 5 -o profile.prof ./binary
```

## Output Format

After each iteration, present:

```markdown
## Iteration X - <Language>

| Metric | Value |
|--------|-------|
| Top Hotspot | <function> (<percentage>%) |
| Execution Time | <time>ms |
| Delta from Previous | <+/-><percent>% |
| Reward | <value> |
| Status | IMPROVED/DEGRADED |

### Recommendation
<What to fix next>
```

## Constraints

- Maximum 4 iterations per language
- Focus on the top 1-2 hotspots per iteration
- Avoid premature optimization
- Verify improvements with profiling before declaring success

## Success Criteria

- Identify and fix at least 2 performance issues
- Achieve measurable improvement (positive reward)
- Maintain functional correctness
