## MODIFIED Requirements

## MODIFIED Requirements

### Requirement: Skill Execution Context
The system SHALL provide skills with access to a shared execution context that includes the project`s `ToolRegistry`. Skills SHALL be able to invoke registered tools (data I/O, describe, script generation, script execution) during AUTO phases. Tool definitions SHALL be dynamically injected into LLM context for each AUTO phase.

#### Scenario: Tool definitions injected for skill execution
- **WHEN** a skill enters an AUTO phase
- **THEN** the LangGraph agent queries `ToolRegistry.get_definitions()` and includes all tool schemas in the LLM request

#### Scenario: Skill invokes data read tool
- **WHEN** a data-cleaning skill`s "Analyze" phase needs to inspect a CSV file
- **THEN** the LLM can call `read_csv` to get the schema and sample, and the result is fed back into the conversation

#### Scenario: Skill generates and executes a script
- **WHEN** a data-cleaning skill`s "Execute" phase needs to run a cleaning script
- **THEN** the LLM calls `generate_script` to create the script, then `execute_script` to run it in the sandbox, and captures the output

### Requirement: Tool-Aware Phase Definitions
The system SHALL support skill phase definitions that declare which tools are available during that phase. Tool availability SHALL be scoped per-phase: a "Generate" phase may have `generate_script` and `execute_script`, while an "Analyze" phase may have `read_csv`, `read_parquet`, and `describe_dataset`.

#### Scenario: Phase-scoped tool availability
- **WHEN** a SKILL.md phase definition includes `tools: [read_csv, describe_dataset]`
- **THEN** only those tools are injected into the LLM context for that phase

#### Scenario: Phase without explicit tools gets all
- **WHEN** a SKILL.md phase definition does not specify tools
- **THEN** all registered tools are available during that phase
