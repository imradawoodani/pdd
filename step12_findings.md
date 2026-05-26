## Identified Issues - Context Optimization (Iteration 2)

### 1. Syntax Issues (Invalid Includes)
- **File:** `pdd/prompts/llm_invoke_python.prompt` (Line 290)
- **File:** `pdd/prompts/context_generator_main_python.prompt` (Line 53)
- **Issue:** Both files contain `<include>../docs/api-documentation.md</include>`, but this file does not exist on disk. The orchestrator flagged this as a "silently dropped" document because it couldn't be resolved.
- **Recommendation:** Remove the invalid include or create the missing documentation file.

### 2. Logical/Inconsistency Issues (Frontend Props)
- **Files:** `pdd/prompts/frontend/components/ArchitectureView_typescriptreact.prompt` vs `pdd/prompts/frontend/components/GraphToolbar_typescriptreact.prompt`
- **Issue:** `ArchitectureView` (Requirement 19) expects a model selection dropdown in `GraphToolbar`, but the `GraphToolbar` prompt lacks the corresponding props (`selectedModel`, `availableModels`, `onModelChange`) and the requirement to implement the dropdown. Iteration 1's claim of fixing frontend prop inconsistencies was incomplete.
- **Recommendation:** Update `GraphToolbar_typescriptreact.prompt` to include the necessary props and the requirement for the model selection dropdown.

### 3. Documentation Issues (Duplication)
- **File:** `docs/prompting_guide.md`
- **Issue:** Contains two nearly identical sections for "Context Window Health Visualization":
    - **Line 140:** "Architecture-Level Context Health"
    - **Line 1537:** "Context Window Health Visualization"
- **Recommendation:** Consolidate these into a single section. The version at line 1537 is more detailed and should be preferred.

### 4. Style Issues (Redundant Model Definitions)
- **File:** `pdd/prompts/server/routes/architecture_python.prompt`
- **Issue:** Explicitly defines Pydantic models (`TokenBreakdown`, `TokenMetrics`, etc.) in its `% Models` section. These are already defined in `pdd/prompts/server/models_python.prompt` (which generates `pdd/server/models.py`).
- **Recommendation:** While common in PDD to help the LLM, these should ideally be imported from `pdd.server.models` to avoid drift if the models change.

### 5. Architecture Registry Health (Flagged by Step 10)
- **File:** `architecture.json`
- **Issue:** Multiple entries have `filepath` values that do not exist on disk (e.g., `extensions/recruiting/resurface_check.py`). 
- **Recommendation:** These should be corrected or the missing files should be generated/removed.

### 6. Orchestrator Warning (Silently Dropped)
- **Issue:** The orchestrator flagged `fallback.md` as silently dropped. 
- **Finding:** This is a false positive; `fallback.md` is used as an example in `agentic_update_python.prompt` and `sync_order_python.prompt` and is intentionally non-existent. No action needed for `fallback.md`, but the logic that flags it might need tuning.
