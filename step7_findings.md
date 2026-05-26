## Step 7: Prompt Classification

**Classification:** Prompt Defect

DEFECT_TYPE: prompt
PROMPT_FIXED: prompts/fix_error_loop_python.prompt

### Analysis
The bug was caused by an omission in the prompt specification for the fix loop. While the `fix_error_loop` function signature in `fix_error_loop_python.prompt` correctly included the `protect_tests` flag, the requirements section failed to instruct the code to propagate this flag to the agentic fallback function (`run_agentic_fix`). Consequently, even when users passed `--protect-tests`, the agentic fallback would incorrectly receive `protect_tests=False` (the default), leading it to believe it had permission to modify test files.

Additionally, the agent prompt templates (`agentic_fix_primary_LLM.prompt` and `agentic_fix_nonpython_LLM.prompt`) lacked the explicit, strong constraints requested by the user to ensure the agent understands it MUST NOT modify files under `tests/`.

### Evidence
- **Prompt specifies:** `fix_error_loop_python.prompt` included `protect_tests` in the interface but lacked a requirement to forward it to the agentic fallback.
- **Code implements:** `pdd/fix_error_loop.py` matched the prompt by invoking `run_agentic_fix` without the flag.
- **User expects:** The `--protect-tests` flag to be honored by all fixing stages, including the agentic fallback.

### Prompt Changes Made
**File:** `prompts/fix_error_loop_python.prompt`
- Added: "Forward the `protect_tests` flag to `run_agentic_fix`." to Requirement 6.

**File:** `prompts/agentic_fix_primary_LLM.prompt` & `prompts/agentic_fix_nonpython_LLM.prompt`
- Enhanced the Test Protection Mode section with explicit constraints: "you MUST NOT modify any file under `tests/` or the test file itself... If your analysis suggests the test file itself is wrong, stop and report this..."

### Conclusion
The prompt specification was incorrect. The prompts have been fixed. Proceeding with test generation based on the corrected specification.

---
*Proceeding to Step 8: Test Plan*
