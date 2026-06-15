## 1. Project Scaffolding

- [ ] 1.1 Initialize Python project structure with FastAPI backend + Vue frontend
- [ ] 1.2 Define `.datamind/` directory schema and `config.yaml` format
- [ ] 1.3 Implement project initialization CLI (`datamind init`)

## 2. Context Engine (Layer 1 Foundation)

- [ ] 2.1 Design SQLite schema for typed nodes (Dataset, Script, Execution) and edges (GENERATED_BY, PRODUCED, USED_INPUT)
- [ ] 2.2 Implement graph database read/write API (insert node, insert edge, query ancestors, query descendants)
- [ ] 2.3 Implement event sourcing: write immutable execution logs to `executions/` directory
- [ ] 2.4 Implement materialized view rebuild from event log

## 3. Data Lineage (Layer 1)

- [ ] 3.1 Implement dataset registration: detect new files in `data/raw/` and `data/processed/`, create Dataset nodes
- [ ] 3.2 Implement auto-describe engine: read CSV/Parquet/Excel, infer types, compute statistics, generate `describe/*.md`
- [ ] 3.3 Implement script-as-edge pattern: parse script I/O to detect input/output datasets, link in graph
- [ ] 3.4 Implement lineage query API: trace ancestors (raw → ... → dataset) and descendants (dataset → ... → all outputs)
- [ ] 3.5 Implement reproducibility: re-run script chain from raw data to reproduce any processed dataset

## 4. Cognitive Journey (Layer 2)

- [ ] 4.1 Implement decision log (`decisions.jsonl`): structured entries with {id, what, why, alternatives, implications, timestamp}
- [ ] 4.2 Implement exploration tree (`exploration.json`): nodes with status tags (SELECTED, REJECTED, EXPLORATORY), parent-child relationships
- [ ] 4.3 Implement parameter registry (`params.json`): auto-extract parameters from scripts, key by script ID and execution run
- [ ] 4.4 Implement discovery feed (`discoveries.jsonl`): chronological entries with {timestamp, tag, finding, linked_code, linked_data}

## 5. Context Assembly (Layer 3)

- [ ] 5.1 Implement context file generator: produce PROJECT.md, DATASETS.md, HISTORY.md, EXPLORATION.md, PARAMS.md from lower layers
- [ ] 5.2 Implement priority-ordered context packer: assemble CONTEXT_MANIFEST.md with Priority 1-4 tiers
- [ ] 5.3 Implement token budget management: truncate/compress lower-priority content when budget exceeded
- [ ] 5.4 Implement checkpoint generator: periodically create CHECKPOINT.md (~2k tokens) summarizing project state
- [ ] 5.5 Implement auto-refresh: regenerate context files after every AI execution that changes state

## 6. Skill System (Layer 4)

- [ ] 6.1 Define SKILL.md format: purpose, inputs, workflow steps (AUTO | GATE), outputs
- [ ] 6.2 Implement skill loader: parse SKILL.md files from `skills/` directory
- [ ] 6.3 Implement skill executor: execute AUTO steps sequentially, pause at GATE steps
- [ ] 6.4 Implement gate approval flow: present proposal to human, accept APPROVE/REJECT/MODIFY
- [ ] 6.5 Create built-in skills: data-cleaning, data-exploration, feature-engineering, model-training, report-generation
- [ ] 6.6 Implement skill pipeline composer: chain skills where outputs of one become inputs of next
- [ ] 6.7 Implement custom skill creation: user-facing interface for defining new SKILL.md files

## 7. Web UI

- [ ] 7.1 Set up Vue project with three-panel layout (sidebar, center chat, right context panel)
- [ ] 7.2 Implement data sidebar: raw/processed folder tree, dataset metadata display, drag-and-drop upload
- [ ] 7.3 Implement chat panel: message display, `/skill` command parsing, code display with syntax highlighting
- [ ] 7.4 Implement gate interaction: APPROVE/REJECT/MODIFY buttons inline in chat
- [ ] 7.5 Implement context panel: live lineage graph visualization, recent decisions list, active parameters display
- [ ] 7.6 Implement session context indicator: show loaded context status, last session time, checkpoint version

## 8. Integration & Polish

- [ ] 8.1 Wire full pipeline: upload dataset → auto-describe → skill invocation → execution → context update → manifest refresh
- [ ] 8.2 Implement context injection for Claude Code MCP integration
- [ ] 8.3 Add project-level tests: end-to-end workflow from raw data to report
- [ ] 8.4 Documentation: user guide, skill authoring guide, project format specification
