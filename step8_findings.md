## Step 8: Test Plan

### Existing Test Coverage
- **Test files:** `tests/test_fix_error_loop.py`, `tests/test_agentic_fix.py`, `tests/test_commands_fix.py`
- **Current coverage:** Covers iterative fixing, basic agentic fallback, and CLI command execution.
- **Gap:** Does not verify propagation of the `protect_tests` flag to the agentic fallback instructions, nor does it verify that the agentic fallback actually enforces test protection (via instruction file content and scope guard reversion).

### Proposed Tests

#### Test 1: fix_error_loop propagates protect_tests to agentic fallback
- **Input:** Call `fix_error_loop` with `protect_tests=True` in a scenario that triggers agentic fallback (e.g., initial test failure or max attempts reached).
- **Expected:** The internal helper `_safe_run_agentic_fix` (which wraps `run_agentic_fix`) is called with `protect_tests=True`.
- **Actual (before fix):** `_safe_run_agentic_fix` does not accept `protect_tests`, causing a `TypeError`, or if it defaults, it remains `False`.

#### Test 2: agentic_fix instruction file content honors protect_tests
- **Input:** Call `run_agentic_fix` with `protect_tests=True`.
- **Expected:** The generated `agentic_fix_instructions.txt` contains `## Test Protection Mode: true` and the explicit constraint text forbidding modification of files under `tests/`.
- **Actual (before fix):** The file contains `## Test Protection Mode: false` and lacks the constraints.

#### Test 3: agentic_fix scope guard reverts unauthorized test changes
- **Input:** Call `run_agentic_fix` with `protect_tests=True`, mocking the agent task to modify both the code file and the test file.
- **Expected:** The code file changes are preserved, but the test file is reverted to its original state by the scope guard.
- **Actual (before fix):** Both changes are preserved because the test file is included in the `allowed_paths` for the scope guard when `protect_tests` is ignored/False.

#### Test 4: CLI fix command propagates --protect-tests flag
- **Input:** Run `pdd fix --loop --protect-tests ...` via `CliRunner`.
- **Expected:** The underlying `fix_main` and subsequently `fix_error_loop` are called with `protect_tests=True`.
- **Actual (before fix):** (Already works at the CLI level, but need to ensure no regressions in the chain to fallback).

#### Test 5: fix_error_loop non-Python fallback honors protect_tests
- **Input:** Call `fix_error_loop` on a non-Python file (e.g., `.js`) with `protect_tests=True`.
- **Expected:** The jump straight to agentic fallback correctly forwards `protect_tests=True` to the agent.
- **Actual (before fix):** Flag is dropped during the direct jump to fallback.

### Test Location
- **Files:**
  - `tests/test_fix_error_loop.py` (Test 1, 5)
  - `tests/test_agentic_fix.py` (Test 2, 3)
  - `tests/test_commands_fix.py` (Test 4)
- **Framework:** pytest

### Notes
- Will use mocks for LLM calls and git porcelain to isolate logic.
- Behavioral verification will rely on checking file system state (instruction files and reverted test files) rather than just signature inspection.

---
*Proceeding to Step 9: Generate Test*
