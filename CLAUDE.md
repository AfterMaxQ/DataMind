# DataMind Studio — Claude Rules of Engagement

## DO

### 1. Follow Comet Phase Discipline
- Read `.comet.yaml` before every action to confirm current phase (open / design / build / verify / archive)
- Respect phase boundaries: open+design → no source code; build → code+tests; verify → validation only; archive → run archive script only
- Transition phases via `comet-guard <name> <phase> --apply`; never manually edit the `phase` field

### 2. Use Subagents in Build Phase
- The main session is coordinator only — do not write code or modify source files directly
- Dispatch one fresh background agent per task (Agent tool with `run_in_background: true`)
- After implementation: spec compliance review first, code quality review second
- Only check off a task and commit after BOTH reviews pass
- Never pause between tasks to summarize or ask "should I continue"

### 3. TDD First
- Every task: write a failing test, watch it fail, then write minimal code to pass
- Fix agents also follow TDD
- Agent reports must include RED/GREEN evidence (failure command + output, pass command + output)

### 4. Commit Discipline
- Commit immediately after each task passes dual review — never batch commits
- `git add` only files relevant to the current change; NEVER `git add -A` (sweeps up pre-existing untracked files on master)
- Commit messages describe what was done

### 5. Write Delta Specs Correctly
- Before writing a delta spec, grep the main spec directory (`openspec/specs/`) to check if the requirement header already exists
- Exists → use `## MODIFIED Requirements`
- Does not exist → use `## ADDED Requirements`
- Headers must match exactly — the archive script compares by string equality

### 6. Configure .comet.yaml Properly
- Python projects must set `build_command` and `verify_command` (e.g., `pytest -q`); the guard cannot auto-detect Python
- `base_ref`, `isolation`, `build_mode`, `subagent_dispatch`, `tdd_mode` — all required; the build exit guard checks every one

### 7. Handle Windows Paths
- Git Bash uses `/f/Python/...` format (not `F:/`)
- Shell commands → `/f/...` format; PowerShell → `F:\...` format; Write/Edit tools → `F:\...` format
- comet-env.sh is at `/f/Python/DataMind-Studio/.claude/skills/comet/scripts/comet-env.sh`

### 8. Persist State
- State machine MUST call `save()` after every phase transition to `.skill.yaml`
- Resume pattern: `agent.run(restored_sm)` binds the state machine first, then `approve_gate()`

### 9. API Design
- FastAPI: store a singleton `Project` on `app.state`; never create a new `Project` per endpoint (model switch is lost)
- Gate approval endpoints must resume agent execution for subsequent AUTO phases after approval

### 10. Verify Before Assuming
- Don't assume the base branch is `main` — run `git branch -a` first (this repo uses `master`)
- Don't assume a remote is configured — run `git remote -v` first
- Don't assume the guard can auto-detect the build system — configure `build_command` explicitly for Python projects

---

## DON'T

### 1. Don't Write Files in Forbidden Phases
- The comet-hook-guard blocks Write/Edit tools during open, design, and archive phases
- **Workaround**: use PowerShell `Set-Content` to bypass the hook (only for delta specs and other must-write artifacts; .comet.yaml changes MUST use `comet-state set`)

### 2. Don't Hand-Edit .comet.yaml
- Use `comet-state set <name> <key> <value>` to update fields
- Use `comet-state transition <name> <event>` to change state
- Manual edits will cause guard validation failures

### 3. Don't Skip Reviews
- Spec compliance review MUST come before code quality review
- A failed review means fix → re-review (same reviewer type); never skip re-review and move on
- Pushing forward with unresolved review issues compounds problems

### 4. Don't Develop Directly on Master
- Always work on a feature branch or in a worktree
- Run the full test suite on the merged result before pushing

### 5. Don't `git add -A`
- This sweeps up pre-existing uncommitted files on master into your commit
- Only `git add` files that belong to the current change
- Before removing a worktree, confirm all changes are committed and merged

### 6. Don't Skip Main Spec Conflict Checks Before Archive
- If a delta spec's ADDED requirement header already exists in the main spec, `comet-archive` will fail
- Fix: change `ADDED` → `MODIFIED` in the delta spec, then re-run the archive script

### 7. Don't Execute Build Tasks in the Main Session
- Under `build_mode: subagent-driven-development`, the main session ONLY coordinates
- All code changes go through background subagents
- Violating this pollutes context and breaks the audit trail

### 8. Don't Assume Library APIs After Two Failures
- If a function call fails twice with the same library, STOP guessing
- Use the Context7 MCP tool (`mcp__plugin_context7_context7__resolve-library-id` → `mcp__plugin_context7_context7__query-docs`) to look up the correct API
- Repeatedly trying wrong signatures wastes time and tokens

### 9. Don't Assume Your Own Code Is Correct — Test It
- Every implementation, every fix, every refactor: run the tests
- If you changed something and didn't run tests, you don't know if it works
- "It looks right" is not a test result

## Behavioral guidelines

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.



## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

