## ADDED Requirements

### Requirement: Tool Registry
The system SHALL provide a `ToolRegistry` that stores all available tool definitions as `(schema, callable)` pairs. Tools SHALL be registered at engine startup. The registry SHALL expose `get_definitions()` returning the full tool schema list for LLM injection, and `execute(name, args)` dispatching execution to the registered callable.

#### Scenario: Register and execute a tool
- **WHEN** a tool is registered with name, JSON schema, and callable
- **THEN** `get_definitions()` includes that tool`s schema and `execute(name, args)` invokes the callable with the given arguments

#### Scenario: Unknown tool returns error
- **WHEN** `execute` is called with a tool name not in the registry
- **THEN** an error result is returned with a message indicating the tool is unknown

### Requirement: Data I/O Tools
The system SHALL provide tools for reading common data formats. Each read tool SHALL accept a file path and return the dataset schema (column names, inferred types) plus a sample of the first N rows (default 10).

#### Scenario: Read CSV with auto-detect
- **WHEN** `read_csv` is called with a path to a valid CSV file
- **THEN** the tool returns column names, inferred dtypes, row count, and first 10 rows as JSON

#### Scenario: Read Parquet file
- **WHEN** `read_parquet` is called with a path to a valid Parquet file
- **THEN** the tool returns the schema and sample rows

#### Scenario: Read Excel file
- **WHEN** `read_excel` is called with a path to a valid Excel file
- **THEN** the tool returns sheet names, schema per sheet, and sample rows

#### Scenario: Read non-existent file returns error
- **WHEN** any read tool is called with a path that does not exist
- **THEN** an error result is returned with a "file not found" message

### Requirement: Auto-Describe Tool
The system SHALL provide a `describe_dataset` tool that auto-generates a data description for any registered dataset. The description SHALL include: row count, column count, column names, inferred types, null counts and percentages, unique value counts, and basic distribution statistics for numeric columns.

#### Scenario: Describe a CSV dataset
- **WHEN** `describe_dataset` is called with a registered dataset path
- **THEN** a description is generated and saved to `describe/<filename>.describe.md`, and the dataset node is created in graph.db

### Requirement: Script Generation Tool
The system SHALL provide a `generate_script` tool that creates Python scripts from templates. The tool SHALL accept a template name, parameters dict, and output path. Generated scripts SHALL be executable and include metadata comments identifying them as AI-generated.

#### Scenario: Generate a cleaning script
- **WHEN** `generate_script` is called with template "data-cleaning", parameters {"input": "sales.csv", "operations": ["drop_nulls", "normalize"]}, and output path "scripts/clean_sales.py"
- **THEN** a valid Python script is written to the output path with the specified operations

### Requirement: Script Execution Sandbox
The system SHALL provide an `execute_script` tool that runs a Python script in a subprocess. Execution SHALL have a configurable timeout (default 300 seconds). Stdout and stderr SHALL be captured and returned. The tool SHALL enforce a maximum output size limit (default 1MB).

#### Scenario: Execute a script successfully
- **WHEN** `execute_script` is called with a valid Python script path
- **THEN** the script runs in a subprocess and stdout, stderr, and exit code are returned

#### Scenario: Script timeout
- **WHEN** a script exceeds the configured timeout
- **THEN** the subprocess is terminated and an error result with "timeout" is returned

#### Scenario: Script with error
- **WHEN** a script raises an exception
- **THEN** the exit code is non-zero and stderr contains the traceback

### Requirement: Tool Definitions for LLM Context
The system SHALL generate OpenAI-compatible tool definitions from the `ToolRegistry` for injection into LLM requests. Each tool definition SHALL include a name, description, and JSON Schema `parameters` object.

#### Scenario: Tool definitions injected into LLM call
- **WHEN** the LangGraph agent prepares an LLM call for an AUTO phase
- **THEN** the `tools` parameter includes definitions for all registered tools
