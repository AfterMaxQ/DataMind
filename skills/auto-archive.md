---
skill: auto-archive
version: 2
---
# Auto Archive

**Purpose:** Automatically organize and archive completed skill session outputs for long-term traceability.

**Inputs:** A completed skill session directory under .datamind/skill-sessions/.

## Workflow

1. **Audit Artifacts** (AUTO) — Scan session directory, verify all phase artifacts exist and are valid
2. **Generate Summary** (AUTO) — Create a human-readable summary of the session: what was done, key results
3. **Organize Outputs** (AUTO) — Move outputs to canonical locations (data/, describe/, scripts/) with linking
4. **Gate: Review Plan** (GATE) — Present archive plan for human review before execution
5. **Execute Archive** (AUTO) — Execute the archive plan, update lineage graph, finalize session

## Outputs

- Session summary in describe/
- Organized artifacts in canonical directories
- Updated lineage graph edges
- Finalized .skill.yaml with archived status
