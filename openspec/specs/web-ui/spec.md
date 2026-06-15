# web-ui Specification

## Purpose
TBD - created by archiving change datamind-core. Update Purpose after archive.
## Requirements
### Requirement: Three-Panel Layout
The system SHALL provide a web interface with three panels: a left sidebar for data and script browsing, a central panel for AI dialogue, and a right panel for context visualization.

#### Scenario: Default layout
- **WHEN** user opens the web UI
- **THEN** all three panels are visible: sidebar (data/files), center (chat), right (lineage + context)

### Requirement: Data Sidebar
The left sidebar SHALL display datasets organized by raw/ and processed/ folders. Each dataset entry SHALL show name, row count, column count, and a link to its generating script (for processed datasets). The sidebar SHALL support drag-and-drop file upload for adding new raw datasets.

#### Scenario: Drag and drop CSV upload
- **WHEN** user drags a CSV file from their desktop onto the sidebar
- **THEN** the file is copied to `data/raw/`, a Dataset node is created in graph.db, and a describe file is auto-generated

#### Scenario: Click processed dataset for lineage
- **WHEN** user clicks a processed dataset in the sidebar
- **THEN** the right panel highlights the dataset's position in the lineage graph and shows its generating script

### Requirement: Chat Panel
The central panel SHALL provide a dialogue interface where users can type messages to the AI, invoke skills with `/skill` commands, and see AI responses including proposed code, analysis results, and gate approval prompts. Generated code SHALL be displayed inline with syntax highlighting.

#### Scenario: Chat interaction
- **WHEN** user types a message in the chat input
- **THEN** the message appears in the conversation and the AI responds based on project context

#### Scenario: Skill invocation display
- **WHEN** user invokes `/skill data-cleaning sales.csv`
- **THEN** the chat shows the skill workflow steps as they execute, with gate prompts rendered as interactive approval buttons

#### Scenario: Code display
- **WHEN** AI generates a processing script
- **THEN** the code is displayed inline with syntax highlighting and a "View in Scripts" link

### Requirement: Context Panel
The right panel SHALL display the live lineage graph, recent decisions from decisions.jsonl, and active parameters from params.json. The lineage graph SHALL update in real-time as new datasets and scripts are created.

#### Scenario: Lineage graph updates
- **WHEN** a new script is generated and executed
- **THEN** the lineage graph in the right panel adds the new node and edge immediately

#### Scenario: Decision log display
- **WHEN** a new decision is recorded in decisions.jsonl
- **THEN** the recent decisions list in the right panel shows the new entry

### Requirement: Session Context Indicator
The web UI SHALL display the current context status: whether context has been loaded, the last session timestamp, the current checkpoint version, and a summary of what was injected.

#### Scenario: Context status display
- **WHEN** a new session starts
- **THEN** the UI shows "Context: Ready ✓" with details of what was injected (datasets, decisions, checkpoint version)

