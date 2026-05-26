## Step 11: Issue Identification (Iteration 3/5)

**Status:** Issues Found

### Issues to Fix

1. **[FILE]** `architecture.json`
   - **Type:** Logic / Registry
   - **Issue:** Multiple entries (e.g., `resurface_check_Python.prompt`, `agentic_bug_step4_reproduce_LLM.prompt`) have `filepath` or `filename` values that do not exist on disk. This was flagged as `ORCHESTRATOR_POSTCHECK_WARNINGS`.
   - **Fix:** Update the registry to reflect current file names and locations (e.g., `agentic_bug_step5_reproduce_LLM.prompt` instead of `step4`) and ensure `filepath` points to existing code or is corrected to the correct prompt path if it's a prompt-only module.

2. **[FILE]** `pdd/prompts/server/token_counter_python.prompt` (Requirement 14 & 15)
   - **Type:** Convention / Ambiguity
   - **Issue:** The logic for discovering "associated test or example files by convention" is not specified. For a project-wide audit, a vague convention could lead to missing or over-counting files.
   - **Fix:** Explicitly define the convention (e.g., "files with the same base name as the prompt found in `tests/`, `context/`, or `examples/` directories").

3. **[FILE]** `pdd/prompts/server/routes/architecture_python.prompt` (Requirement 8)
   - **Type:** Convention / Ambiguity
   - **Issue:** The audit aggregates results into a mapping of `filepath -> ContextAudit`. While `filepath` is unique, the frontend often identifies modules by `filename` (the prompt basename).
   - **Fix:** Ensure the frontend correctly lookups by `filepath` or switch the mapping key to `filename` for better alignment with existing frontend patterns.

4. **[FILE]** `pdd/prompts/server/routes/architecture_python.prompt` (Dependencies)
   - **Type:** Convention
   - **Issue:** The prompt lists `token_counter_python.prompt` as a PDD dependency but doesn't include its interface in the `% Dependencies` section. The LLM won't have the signature for `get_context_audit` when generating the route.
   - **Fix:** Add `<include select="interface">pdd/prompts/server/token_counter_python.prompt</include>` to the `% Dependencies` section.

5. **[FILE]** `pdd/prompts/server/token_counter_python.prompt` (Requirement 15)
   - **Type:** Logic
   - **Issue:** Requirement 15 says to "Hydrate the prompt (preprocess)" and then "Calculate TokenMetrics including a heuristic breakdown using a 'File-Level Approximation' strategy (tokenizing files individually)". Hydrating the prompt merges all content, making it difficult to attribute tokens back to their source files.
   - **Fix:** Specify that the breakdown should be calculated by tokenizing the original prompt's `<include>` and `<web>` tag targets separately, *before* or *independent* of full hydration.

6. **[FILE]** `pdd/templates/generic/generate_prompt.prompt`
   - **Type:** Syntax
   - **Issue:** Stale invalid include `<include>docs/api-documentation.md</include>` persists in this template.
   - **Fix:** Remove the invalid include.

7. **[FILE]** `pdd/prompts/server/token_counter_python.prompt` (Requirement 14)
   - **Type:** Logic
   - **Issue:** `get_tree_hash` only mentions `<include>` tags but should also handle `<include-many>` tags to correctly detect all dependencies for hashing.
   - **Fix:** Update the requirement to include both `<include>` and `<include-many>` tags.

8. **[FILE]** `pdd/prompts/frontend/components/ArchitectureView_typescriptreact.prompt` (Requirement 18)
   - **Type:** Ambiguity
   - **Issue:** Requirement 18 says modules are "color-coded" in Context Pressure View but doesn't specify if this is done by passing colors to `ModuleNode` or some other way.
   - **Fix:** Clarify that color-coding is implemented by passing specific status-based colors (Green/Yellow/Red) to the `ModuleNode` via its `data.colors` prop when in this mode.

9. **[FILE]** `pdd/prompts/server/routes/prompts_python.prompt` (Requirement 2)
   - **Type:** Style
   - **Issue:** Explicitly defines Pydantic models (`TokenBreakdown`, `TokenMetrics`, etc.) in its requirements. These are already defined in `pdd/prompts/server/models_python.prompt`.
   - **Fix:** Instruct the model to import these from `pdd.server.models` instead of re-defining them.

### Summary
Found 9 issues requiring fixes.

---
*Proceeding to Step 12: Fix Issues*
