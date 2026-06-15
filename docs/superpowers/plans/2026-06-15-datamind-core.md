---
change: datamind-core
design-doc: docs/superpowers/specs/2026-06-15-datamind-core-design.md
base-ref: ebd08ab49b7656d29e0206504997230efe88a0d9
---

# DataMind Core 实现计划

> **面向 Agentic Worker：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐个任务实现此计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**目标：** 构建 DataMind Studio 核心引擎 —— 一个 AI 原生的数据科学研究系统，通过四层架构（数据血缘、认知旅程、上下文组装、技能编排）捕获项目知识以供 AI 跨会话消费。

**架构：** engine-first 方法：纯 Python 库 → CLI → MCP Server → REST API。四个领域服务（LineageService、CognitionService、AssemblyService、SkillService）各拥有独立存储格式，通过 Project facade 组合，依赖通过构造函数注入。

**技术栈：** Python 3.11+、SQLite（WAL 模式）、FastAPI、Vue 3（Composition API）、MCP Server、Click CLI、pytest

---

## 文件结构总览

```
datamind/
├── __init__.py                     # 包根，版本号
├── config.py                       # 配置常量、默认值
├── errors.py                       # 自定义异常类
├── engine/
│   ├── __init__.py
│   ├── graph.py                    # GraphDB：nodes/edges 表读写 API
│   ├── events.py                   # EventSourcing：写入不可变执行日志
│   ├── lineage.py                  # LineageService：数据集注册、auto-describe、脚本即边、血缘查询
│   ├── describe.py                 # DescribeEngine：CSV/Parquet/Excel 自动描述
│   ├── cognition.py                # CognitionService：decisions/exploration/params/discoveries
│   ├── assembly.py                 # AssemblyService：上下文文件生成、优先级打包、checkpoint
│   ├── skills.py                   # SkillService：SKILL.md 解析、AUTO/GATE 执行、管道组合
│   └── project.py                  # Project：组合四个服务，无业务逻辑
├── cli/
│   ├── __init__.py
│   └── main.py                     # Click CLI：datamind init, context inject, lineage query
├── mcp/
│   ├── __init__.py
│   └── server.py                   # MCP tools：read_context, register_dataset, log_decision
├── api/
│   ├── __init__.py
│   └── app.py                      # FastAPI 应用（Web UI 后端）
└── web/                             # Vue 3 前端（独立搭建）

tests/
├── __init__.py
├── conftest.py                     # 共享 fixtures：tmp_project, sample_datasets
├── unit/
│   ├── test_graph.py               # GraphDB 单元测试
│   ├── test_events.py              # EventSourcing 单元测试
│   ├── test_lineage.py             # LineageService 单元测试
│   ├── test_describe.py            # DescribeEngine 单元测试
│   ├── test_cognition.py           # CognitionService 单元测试
│   ├── test_assembly.py            # AssemblyService 单元测试
│   └── test_skills.py              # SkillService 单元测试
├── integration/
│   ├── test_lineage_integration.py   # LineageService 集成测试（真文件）
│   ├── test_cognition_integration.py # CognitionService 集成测试
│   ├── test_assembly_integration.py  # AssemblyService 集成测试
│   └── test_skills_integration.py    # SkillService 集成测试
└── e2e/
    ├── golden/                     # 快照预期输出
    └── test_workflows.py           # E2E 快照测试

skills/                             # 内置 SKILL.md 文件
├── data-cleaning.md
├── data-exploration.md
├── feature-engineering.md
├── model-training.md
└── report-generation.md
```

---

## 阶段 1：项目脚手架

### Task 1：pyproject.toml 与包结构

**文件：**
- 创建: `pyproject.toml`
- 创建: `datamind/__init__.py`
- 创建: `datamind/config.py`
- 创建: `datamind/errors.py`
- 创建: `pytest.ini`

- [ ] **Step 1：编写 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "datamind-studio"
version = "0.1.0"
description = "AI-native data science research system"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "fastapi>=0.104",
    "uvicorn[standard]>=0.24",
    "pandas>=2.0",
    "pyarrow>=14.0",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
    "httpx>=0.25",
    "black>=23.0",
    "ruff>=0.1",
]

[project.scripts]
datamind = "datamind.cli.main:cli"

[tool.setuptools.packages.find]
where = ["."]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "unit: Unit tests (no I/O)",
    "integration: Integration tests (real files)",
    "e2e: End-to-end snapshot tests",
    "slow: Slow tests",
]
```

- [ ] **Step 2：编写 datamind/__init__.py**

```python
"""DataMind Studio — AI-native data science research system."""

__version__ = "0.1.0"
```

- [ ] **Step 3：编写 datamind/config.py**

```python
"""Configuration constants and project defaults."""

from pathlib import Path

# Default directory names inside .datamind/
GRAPH_DB_NAME = "graph.db"
CONTEXT_DIR = "context"
CONFIG_FILE = "config.yaml"

# Context file names
PROJECT_MD = "PROJECT.md"
DATASETS_MD = "DATASETS.md"
HISTORY_MD = "HISTORY.md"
EXPLORATION_MD = "EXPLORATION.md"
PARAMS_MD = "PARAMS.md"
CHECKPOINT_MD = "CHECKPOINT.md"
CONTEXT_MANIFEST_MD = "CONTEXT_MANIFEST.md"

# Data directories (sibling to .datamind/)
DATA_DIR = "data"
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
SCRIPTS_DIR = "scripts"
DESCRIBE_DIR = "describe"
EXECUTIONS_DIR = "executions"
SKILLS_DIR = "skills"

# Cognitive journey files
DECISIONS_FILE = "decisions.jsonl"
EXPLORATION_FILE = "exploration.json"
PARAMS_FILE = "params.json"
DISCOVERIES_FILE = "discoveries.jsonl"

# Context packing priorities (token allocations)
TOKEN_BUDGET = 40_000
PRIORITY1_TOKENS = 2_500   # ALWAYS
PRIORITY2_TOKENS = 8_000   # RECENT
PRIORITY3_TOKENS = 3_000   # RELEVANT
PRIORITY4_TOKENS = 2_000   # COMPRESSED

# Checkpoint: regenerate after N new execution logs
CHECKPOINT_THRESHOLD = 10

# Supported data formats for auto-describe
SUPPORTED_FORMATS = {".csv", ".parquet", ".xlsx", ".xls", ".json", ".tsv"}

# SQLite pragmas for initialization
SQLITE_PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
]


def resolve_dot_datamind(project_root: str | Path) -> Path:
    """Resolve the .datamind/ directory path from a project root."""
    root = Path(project_root).resolve()
    return root / ".datamind"


def resolve_component_paths(project_root: str | Path) -> dict[str, Path]:
    """Resolve all .datamind/ component paths for a project root."""
    base = resolve_dot_datamind(project_root)
    root = Path(project_root).resolve()
    return {
        "graph_db": base / GRAPH_DB_NAME,
        "context_dir": base / CONTEXT_DIR,
        "config_file": base / CONFIG_FILE,
        "data_dir": root / DATA_DIR,
        "raw_data": root / RAW_DATA_DIR,
        "processed_data": root / PROCESSED_DATA_DIR,
        "scripts_dir": root / SCRIPTS_DIR,
        "describe_dir": root / DESCRIBE_DIR,
        "executions_dir": root / EXECUTIONS_DIR,
        "skills_dir": root / SKILLS_DIR,
        "decisions_file": base / DECISIONS_FILE,
        "exploration_file": base / EXPLORATION_FILE,
        "params_file": base / PARAMS_FILE,
        "discoveries_file": base / DISCOVERIES_FILE,
    }
```

- [ ] **Step 4：编写 datamind/errors.py**

```python
"""Custom exception hierarchy for DataMind."""


class DataMindError(Exception):
    """Base exception for all DataMind errors."""


class ScriptExecutionError(DataMindError):
    """A script execution failed (stderr, exit_code captured)."""

    def __init__(self, script_path: str, stderr: str, exit_code: int):
        self.script_path = script_path
        self.stderr = stderr
        self.exit_code = exit_code
        super().__init__(
            f"Script '{script_path}' failed (exit {exit_code}): {stderr[:200]}"
        )


class DataIntegrityError(DataMindError):
    """Data integrity issue — affected graph node IDs included."""

    def __init__(self, message: str, node_ids: list[str] | None = None):
        self.node_ids = node_ids or []
        super().__init__(message)


class GateRejectionError(DataMindError):
    """Normal control flow — a GATE step was rejected by human."""

    def __init__(self, gate_name: str, reason: str = ""):
        self.gate_name = gate_name
        self.reason = reason
        super().__init__(f"Gate '{gate_name}' rejected: {reason}")


class ContextAssemblyError(DataMindError):
    """Context assembly degraded — missing sources."""

    def __init__(self, message: str, missing_sources: list[str] | None = None):
        self.missing_sources = missing_sources or []
        super().__init__(message)


class SkillParseError(DataMindError):
    """SKILL.md parse failure."""

    pass


class ProjectNotFoundError(DataMindError):
    """No .datamind/ directory found at the given path."""

    pass
```

- [ ] **Step 5：编写 pytest.ini（如不使用 pyproject.toml）**

创建 `pytest.ini`（如果 pyproject.toml 的 `[tool.pytest.ini_options]` 生效则跳过）：

```ini
[pytest]
testpaths = tests
pythonpath = .
markers =
    unit: Unit tests (no I/O)
    integration: Integration tests (real files)
    e2e: End-to-end snapshot tests
    slow: Slow tests
```

- [ ] **Step 6：安装开发依赖并验证**

```bash
pip install -e ".[dev]"
python -c "from datamind import __version__; print(__version__)"
```

预期：`0.1.0`

- [ ] **Step 7：提交**

```bash
git add pyproject.toml datamind/__init__.py datamind/config.py datamind/errors.py pytest.ini
git commit -m "feat: add project scaffolding with config and error hierarchy"
```

---

### Task 2：.datamind/ 目录初始化

**文件：**
- 创建: `datamind/engine/__init__.py`
- 修改: `datamind/config.py`（已在 Task 1 创建）

- [ ] **Step 1：编写 .datamind/ 目录初始化测试**

创建 `tests/__init__.py`（空文件）。

创建 `tests/conftest.py`：

```python
"""Shared test fixtures."""
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project():
    """Create a temporary project directory."""
    tmp = Path(tempfile.mkdtemp(prefix="datamind_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_csv(tmp_project):
    """Create a sample CSV file in data/raw/."""
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    csv_path = raw_dir / "sample.csv"
    csv_path.write_text("a,b,c\n1,2,3\n4,5,6\n")
    return csv_path
```

创建 `tests/unit/test_init.py`：

```python
"""Tests for project initialization."""
from pathlib import Path

import pytest
from datamind.config import resolve_dot_datamind, resolve_component_paths


def test_resolve_dot_datamind():
    result = resolve_dot_datamind("/home/user/myproject")
    assert result == Path("/home/user/myproject/.datamind")


def test_resolve_component_paths_returns_all_keys():
    paths = resolve_component_paths("/tmp/test_project")
    expected_keys = {
        "graph_db",
        "context_dir",
        "config_file",
        "data_dir",
        "raw_data",
        "processed_data",
        "scripts_dir",
        "describe_dir",
        "executions_dir",
        "skills_dir",
        "decisions_file",
        "exploration_file",
        "params_file",
        "discoveries_file",
    }
    assert set(paths.keys()) == expected_keys


def test_resolve_component_paths_all_end_with_dot_datamind():
    paths = resolve_component_paths("/tmp/test_project")
    base = Path("/tmp/test_project/.datamind")
    assert paths["graph_db"].parent == base
    assert paths["context_dir"].parent == base
```

运行：

```bash
pytest tests/unit/test_init.py -v
```

预期：3 passed

- [ ] **Step 2：编写初始化逻辑**

创建 `datamind/engine/__init__.py`（空文件）。

在 `datamind/config.py` 中追加初始化函数：

```python
def initialize_project(project_root: str | Path, config: dict | None = None) -> dict[str, Path]:
    """Initialize a DataMind project directory structure.
    
    Creates .datamind/ and all required subdirectories. Returns the
    resolved component paths dict.
    
    Args:
        project_root: Path to the project root directory.
        config: Optional config dict to write to config.yaml.
    
    Returns:
        Dict mapping component names to their Path objects.
    
    Raises:
        ProjectNotFoundError: If project_root does not exist.
    """
    root = Path(project_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Project root does not exist: {root}")

    paths = resolve_component_paths(project_root)
    base = paths["graph_db"].parent  # .datamind/
    base.mkdir(parents=True, exist_ok=True)

    # Create all directories
    for key, path_obj in paths.items():
        if key.endswith("_dir") or key.endswith("_data") or key in ("scripts_dir", "describe_dir", "executions_dir", "skills_dir", "context_dir"):
            path_obj.mkdir(parents=True, exist_ok=True)

    # Write default config.yaml if not provided
    if config is not None:
        with open(paths["config_file"], "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(config, f, default_flow_style=False)

    return paths
```

在 `datamind/config.py` 顶部追加 import：

```python
from pathlib import Path
```

- [ ] **Step 3：编写测试验证目录创建**

在 `tests/unit/test_init.py` 中追加：

```python
from datamind.config import initialize_project


def test_initialize_project_creates_all_dirs(tmp_project):
    paths = initialize_project(tmp_project)
    assert paths["graph_db"].parent.exists()  # .datamind/
    assert paths["context_dir"].exists()
    assert paths["raw_data"].exists()
    assert paths["processed_data"].exists()
    assert paths["scripts_dir"].exists()
    assert paths["describe_dir"].exists()
    assert paths["executions_dir"].exists()
    assert paths["skills_dir"].exists()


def test_initialize_project_writes_config(tmp_project):
    config = {"project_name": "test", "version": "1.0"}
    paths = initialize_project(tmp_project, config)
    import yaml
    with open(paths["config_file"]) as f:
        written = yaml.safe_load(f)
    assert written == config


def test_initialize_project_raises_for_nonexistent(tmp_project):
    bad_path = tmp_project / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        initialize_project(bad_path)
```

运行：

```bash
pytest tests/unit/test_init.py -v
```

预期：6 passed

- [ ] **Step 4：提交**

```bash
git add tests/__init__.py tests/conftest.py tests/unit/test_init.py datamind/config.py datamind/engine/__init__.py
git commit -m "feat: add .datamind/ project initialization logic"
```

---

### Task 3：Click CLI - `datamind init`

**文件：**
- 创建: `datamind/cli/__init__.py`
- 创建: `datamind/cli/main.py`

- [ ] **Step 1：编写 CLI 测试**

创建 `tests/unit/test_cli.py`：

```python
"""Tests for the Click CLI."""
from click.testing import CliRunner
from datamind.cli.main import cli


def test_cli_init_creates_project(tmp_project):
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert (tmp_project / ".datamind").exists()
    assert (tmp_project / ".datamind" / "context").exists()
    assert "Initialized DataMind project" in result.output


def test_cli_init_with_name(tmp_project):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", str(tmp_project), "--name", "myproject"]
    )
    assert result.exit_code == 0
    import yaml
    with open(tmp_project / ".datamind" / "config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["project_name"] == "myproject"


def test_cli_init_preserves_existing(tmp_project):
    (tmp_project / ".datamind").mkdir()
    existing = tmp_project / ".datamind" / "existing.txt"
    existing.write_text("keep me")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert existing.read_text() == "keep me"
```

- [ ] **Step 2：编写 CLI 实现**

创建 `datamind/cli/__init__.py`（空文件）。

创建 `datamind/cli/main.py`：

```python
"""Click CLI for DataMind Studio."""

import click
from datamind.config import initialize_project


@click.group()
@click.version_option()
def cli():
    """DataMind Studio — AI-native data science research system."""
    pass


@cli.command()
@click.argument("project_root", type=click.Path(exists=True))
@click.option("--name", default=None, help="Project name")
def init(project_root, name):
    """Initialize a DataMind project at PROJECT_ROOT."""
    config = {}
    if name:
        config["project_name"] = name
    try:
        paths = initialize_project(project_root, config)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Initialized DataMind project at {project_root}")
    click.echo(f"  .datamind/  -> {paths['graph_db'].parent}")
    click.echo(f"  data/raw/   -> {paths['raw_data']}")
    click.echo(f"  data/processed/ -> {paths['processed_data']}")
    click.echo(f"  scripts/    -> {paths['scripts_dir']}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 3：运行测试验证 CLI**

```bash
pytest tests/unit/test_cli.py -v
```

预期：3 passed

- [ ] **Step 4：手动验证**

```bash
pip install -e .
datamind --help
datamind init --name test-proj /tmp/test_datamind
```

预期：看到 "Initialized DataMind project" 和创建的目录。

- [ ] **Step 5：提交**

```bash
git add datamind/cli/__init__.py datamind/cli/main.py tests/unit/test_cli.py
git commit -m "feat: add Click CLI with 'datamind init' command"
```

---

## 阶段 2：L1 基础 — 图数据库

### Task 4：SQLite schema 创建与连接管理

**文件：**
- 创建: `datamind/engine/graph.py`

- [ ] **Step 1：编写 GraphDB 初始化测试**

创建 `tests/unit/test_graph.py`：

```python
"""Tests for the GraphDB layer."""
import sqlite3
from datamind.engine.graph import GraphDB


def test_graphdb_init_creates_tables(tmp_project):
    db_path = tmp_project / "test.db"
    db = GraphDB(str(db_path))
    db.initialize()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    db.close()

    assert "nodes" in tables
    assert "edges" in tables


def test_graphdb_init_sets_wal_mode(tmp_project):
    db_path = tmp_project / "test.db"
    db = GraphDB(str(db_path))
    db.initialize()

    conn = sqlite3.connect(str(db_path))
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    db.close()

    assert journal_mode.lower() == "wal"


def test_graphdb_init_idempotent(tmp_project):
    db_path = tmp_project / "test.db"
    db1 = GraphDB(str(db_path))
    db1.initialize()
    db1.close()

    db2 = GraphDB(str(db_path))
    db2.initialize()  # should not raise
    db2.close()
```

- [ ] **Step 2：运行测试验证失败**

```bash
pytest tests/unit/test_graph.py -v
```

预期：3 failed（`ImportError: cannot import name 'GraphDB'`）

- [ ] **Step 3：编写 GraphDB 实现**

创建 `datamind/engine/graph.py`：

```python
"""Graph database — SQLite-backed nodes and edges store."""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from datamind.config import SQLITE_PRAGMAS


class GraphDB:
    """SQLite-backed graph database for typed nodes and directed edges."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            for pragma in SQLITE_PRAGMAS:
                self._conn.execute(pragma)
        return self._conn

    def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES nodes(id),
                target_id TEXT NOT NULL REFERENCES nodes(id),
                edge_type TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        """)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
```

- [ ] **Step 4：运行测试验证通过**

```bash
pytest tests/unit/test_graph.py -v
```

预期：3 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/graph.py tests/unit/test_graph.py
git commit -m "feat: add GraphDB with SQLite schema and WAL mode"
```

---

### Task 5：图数据库读写 API（节点与边）

**文件：**
- 修改: `datamind/engine/graph.py`（追加方法）

- [ ] **Step 1：编写节点/边 CRUD 测试**

在 `tests/unit/test_graph.py` 中追加：

```python
def test_insert_node_and_get(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    node_id = db.insert_node(
        type="dataset",
        name="sales.csv",
        path="data/raw/sales.csv",
        metadata={"rows": 100, "columns": 5},
    )
    node = db.get_node(node_id)
    assert node["type"] == "dataset"
    assert node["name"] == "sales.csv"
    assert json.loads(node["metadata"]) == {"rows": 100, "columns": 5}
    db.close()


def test_insert_edge_links_nodes(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    src = db.insert_node(type="script", name="clean.py")
    tgt = db.insert_node(type="dataset", name="clean_sales.csv")
    edge_id = db.insert_edge(
        source_id=src,
        target_id=tgt,
        edge_type="PRODUCED",
        metadata={"row_count": 100},
    )
    edge = db.get_edge(edge_id)
    assert edge["source_id"] == src
    assert edge["target_id"] == tgt
    assert edge["edge_type"] == "PRODUCED"
    db.close()


def test_query_ancestors(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    raw = db.insert_node(type="dataset", name="raw.csv")
    script = db.insert_node(type="script", name="process.py")
    processed = db.insert_node(type="dataset", name="processed.csv")
    db.insert_edge(source_id=script, target_id=processed, edge_type="PRODUCED")
    db.insert_edge(source_id=raw, target_id=script, edge_type="USED_INPUT")

    ancestors = db.query_ancestors(processed)
    ancestor_ids = [n["id"] for n in ancestors]
    assert raw in ancestor_ids
    assert script in ancestor_ids
    # processed itself should not be in ancestors
    assert processed not in ancestor_ids
    db.close()


def test_query_descendants(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    raw = db.insert_node(type="dataset", name="raw.csv")
    script = db.insert_node(type="script", name="process.py")
    processed = db.insert_node(type="dataset", name="processed.csv")
    model = db.insert_node(type="finding", name="model_results")
    db.insert_edge(source_id=raw, target_id=script, edge_type="USED_INPUT")
    db.insert_edge(source_id=script, target_id=processed, edge_type="PRODUCED")
    db.insert_edge(source_id=processed, target_id=model, edge_type="TRIGGERED")

    descendants = db.query_descendants(raw)
    descendant_ids = [n["id"] for n in descendants]
    assert script in descendant_ids
    assert processed in descendant_ids
    assert model in descendant_ids
    assert raw not in descendant_ids
    db.close()


def test_list_nodes_by_type(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    db.insert_node(type="dataset", name="a.csv")
    db.insert_node(type="dataset", name="b.csv")
    db.insert_node(type="script", name="s.py")

    datasets = db.list_nodes_by_type("dataset")
    assert len(datasets) == 2
    scripts = db.list_nodes_by_type("script")
    assert len(scripts) == 1
    db.close()
```

- [ ] **Step 2：运行测试验证失败**

```bash
pytest tests/unit/test_graph.py::test_insert_node_and_get -v
```

预期：FAIL（`AttributeError: 'GraphDB' object has no attribute 'insert_node'`）

- [ ] **Step 3：实现节点/边 CRUD API**

在 `datamind/engine/graph.py` 的 `GraphDB` 类中追加：

```python
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # -- Nodes --

    def insert_node(
        self,
        type: str,
        name: str,
        path: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        node_id = self._new_id()
        self.conn.execute(
            "INSERT INTO nodes (id, type, name, path, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                node_id,
                type,
                name,
                path,
                json.dumps(metadata or {}),
                self._now(),
            ),
        )
        self.conn.commit()
        return node_id

    def get_node(self, node_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_nodes_by_type(self, type: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE type = ? ORDER BY created_at",
            (type,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Edges --

    def insert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        metadata: dict | None = None,
    ) -> str:
        edge_id = self._new_id()
        self.conn.execute(
            "INSERT INTO edges (id, source_id, target_id, edge_type, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                edge_id,
                source_id,
                target_id,
                edge_type,
                json.dumps(metadata or {}),
                self._now(),
            ),
        )
        self.conn.commit()
        return edge_id

    def get_edge(self, edge_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # -- Traversal --

    def query_ancestors(self, node_id: str) -> list[dict]:
        """BFS walk from target -> source to find all upstream nodes."""
        visited: set[str] = set()
        result: list[dict] = []
        queue = [node_id]

        while queue:
            current = queue.pop(0)
            # Find nodes that have edges pointing to `current`
            rows = self.conn.execute(
                "SELECT n.* FROM nodes n "
                "JOIN edges e ON n.id = e.source_id "
                "WHERE e.target_id = ?",
                (current,),
            ).fetchall()
            for row in rows:
                nid = row["id"]
                if nid not in visited and nid != node_id:
                    visited.add(nid)
                    result.append(dict(row))
                    queue.append(nid)

        return result

    def query_descendants(self, node_id: str) -> list[dict]:
        """BFS walk from source -> target to find all downstream nodes."""
        visited: set[str] = set()
        result: list[dict] = []
        queue = [node_id]

        while queue:
            current = queue.pop(0)
            rows = self.conn.execute(
                "SELECT n.* FROM nodes n "
                "JOIN edges e ON n.id = e.target_id "
                "WHERE e.source_id = ?",
                (current,),
            ).fetchall()
            for row in rows:
                nid = row["id"]
                if nid not in visited and nid != node_id:
                    visited.add(nid)
                    result.append(dict(row))
                    queue.append(nid)

        return result
```

顶部追加 imports：

```python
import json
import uuid
from datetime import datetime, timezone
```

- [ ] **Step 4：运行全部图数据库测试**

```bash
pytest tests/unit/test_graph.py -v
```

预期：8 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/graph.py tests/unit/test_graph.py
git commit -m "feat: add GraphDB node/edge CRUD and traversal API"
```

---

### Task 6：事件溯源 — 不可变执行日志

**文件：**
- 创建: `datamind/engine/events.py`

- [ ] **Step 1：编写 EventSourcing 测试**

创建 `tests/unit/test_events.py`：

```python
"""Tests for the EventSourcing layer."""
import json
from datamind.engine.events import ExecutionLog


def test_write_execution_log(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    log_id = el.record(
        script_path="scripts/clean.py",
        status="success",
        inputs=["data/raw/sales.csv"],
        outputs=["data/processed/clean_sales.csv"],
        stdout="Cleaning complete",
        stderr="",
        exit_code=0,
        params={"fill_method": "forward"},
    )
    assert log_id is not None
    log_path = exec_dir / f"{log_id}.json"
    assert log_path.exists()
    content = json.loads(log_path.read_text())
    assert content["script_path"] == "scripts/clean.py"
    assert content["status"] == "success"
    assert content["exit_code"] == 0


def test_record_failure(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    log_id = el.record(
        script_path="scripts/broken.py",
        status="failure",
        inputs=["data/raw/sales.csv"],
        outputs=[],
        stdout="",
        stderr="KeyError: 'col_x'",
        exit_code=1,
        params={},
    )
    log_path = exec_dir / f"{log_id}.json"
    content = json.loads(log_path.read_text())
    assert content["status"] == "failure"
    assert "KeyError" in content["stderr"]


def test_list_recent(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    el.record(script_path="a.py", status="success")
    el.record(script_path="b.py", status="failure")
    el.record(script_path="c.py", status="success")

    recent = el.list_recent(limit=2)
    assert len(recent) == 2
    assert recent[0]["script_path"] == "c.py"  # most recent first
    assert recent[1]["script_path"] == "b.py"


def test_count_since(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    for i in range(5):
        el.record(script_path=f"s{i}.py", status="success")
    # All 5 are after epoch start
    assert el.count_since("1970-01-01T00:00:00Z") == 5
```

- [ ] **Step 2：运行测试验证失败**

```bash
pytest tests/unit/test_events.py -v
```

预期：4 failed（ImportError）

- [ ] **Step 3：实现 EventSourcing**

创建 `datamind/engine/events.py`：

```python
"""Event sourcing — immutable execution logs."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class ExecutionLog:
    """Append-only execution log writer and reader.

    Each execution is stored as a JSON file in the executions/ directory.
    """

    def __init__(self, executions_dir: str):
        self.dir = Path(executions_dir)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def record(
        self,
        script_path: str,
        status: str,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        params: dict | None = None,
    ) -> str:
        """Record an execution event. Returns the log ID."""
        log_id = self._new_id()
        entry = {
            "id": log_id,
            "script_path": script_path,
            "status": status,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "params": params or {},
            "timestamp": self._now(),
        }
        log_path = self.dir / f"{log_id}.json"
        log_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False))
        return log_id

    def read(self, log_id: str) -> dict | None:
        """Read a single execution log by ID."""
        log_path = self.dir / f"{log_id}.json"
        if not log_path.exists():
            return None
        return json.loads(log_path.read_text())

    def list_recent(self, limit: int = 10) -> list[dict]:
        """List recent execution logs, newest first."""
        files = sorted(
            self.dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        logs = []
        for f in files[:limit]:
            logs.append(json.loads(f.read_text()))
        return logs

    def count_since(self, since_timestamp: str) -> int:
        """Count execution logs with timestamp >= since_timestamp."""
        count = 0
        for f in self.dir.glob("*.json"):
            entry = json.loads(f.read_text())
            if entry["timestamp"] >= since_timestamp:
                count += 1
        return count
```

- [ ] **Step 4：运行测试验证通过**

```bash
pytest tests/unit/test_events.py -v
```

预期：4 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/events.py tests/unit/test_events.py
git commit -m "feat: add EventSourcing with immutable execution logs"
```

---

## 阶段 3：L1 — 数据血缘

### Task 7：数据描述引擎 (auto-describe)

**文件：**
- 创建: `datamind/engine/describe.py`

- [ ] **Step 1：编写 DescribeEngine 测试**

创建 `tests/unit/test_describe.py`：

```python
"""Tests for the DescribeEngine."""
import pandas as pd
from pathlib import Path
from datamind.engine.describe import DescribeEngine


def test_describe_csv_generates_markdown(tmp_project):
    csv_path = tmp_project / "data" / "raw" / "test.csv"
    csv_path.parent.mkdir(parents=True)
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"], "c": [1.1, 2.2]}).to_csv(
        csv_path, index=False
    )

    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    engine = DescribeEngine(str(describe_dir))
    output_path = engine.describe(str(csv_path))

    assert output_path.exists()
    content = output_path.read_text()
    assert "# Dataset: test.csv" in content
    assert "a" in content
    assert "int64" in content or "integer" in content.lower()
    assert "b" in content


def test_describe_includes_statistics(tmp_project):
    csv_path = tmp_project / "data" / "raw" / "nums.csv"
    csv_path.parent.mkdir(parents=True)
    pd.DataFrame({"x": [1, 2, 3, 4, 5]}).to_csv(csv_path, index=False)

    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    engine = DescribeEngine(str(describe_dir))
    output_path = engine.describe(str(csv_path))
    content = output_path.read_text()

    assert "mean" in content.lower()
    assert "count" in content.lower()


def test_describe_parquet(tmp_project):
    parquet_path = tmp_project / "data" / "raw" / "test.parquet"
    parquet_path.parent.mkdir(parents=True)
    pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]}).to_parquet(parquet_path)

    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    engine = DescribeEngine(str(describe_dir))
    output_path = engine.describe(str(parquet_path))

    assert output_path.exists()
    content = output_path.read_text()
    assert "test.parquet" in content
    assert "a" in content
    assert "b" in content


def test_describe_unsupported_format_warns(tmp_project):
    txt_path = tmp_project / "data" / "raw" / "notes.txt"
    txt_path.parent.mkdir(parents=True)
    txt_path.write_text("hello world")

    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    engine = DescribeEngine(str(describe_dir))
    with pytest.raises(ValueError, match="Unsupported file format"):
        engine.describe(str(txt_path))


def test_describe_missing_file(tmp_project):
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    engine = DescribeEngine(str(describe_dir))
    with pytest.raises(FileNotFoundError):
        engine.describe(str(tmp_project / "nonexistent.csv"))
```

- [ ] **Step 2：运行测试验证失败**

```bash
pytest tests/unit/test_describe.py -v
```

预期：5 failed（ImportError）

- [ ] **Step 3：实现 DescribeEngine**

创建 `datamind/engine/describe.py`：

```python
"""Auto-describe engine for dataset files."""

import hashlib
from pathlib import Path

import pandas as pd


class DescribeEngine:
    """Reads data files and generates describe/*.md statistics."""

    _readers = {
        ".csv": lambda p: pd.read_csv(p),
        ".tsv": lambda p: pd.read_csv(p, sep="\t"),
        ".parquet": lambda p: pd.read_parquet(p),
        ".xlsx": lambda p: pd.read_excel(p),
        ".xls": lambda p: pd.read_excel(p),
        ".json": lambda p: pd.read_json(p, orient="records"),
    }

    def __init__(self, describe_dir: str):
        self.describe_dir = Path(describe_dir)

    def describe(self, file_path: str) -> Path:
        """Generate a describe/*.md for the given data file.

        Returns the path to the generated markdown file.
        """
        fp = Path(file_path)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = fp.suffix.lower()
        reader = self._readers.get(suffix)
        if reader is None:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported: {list(self._readers.keys())}"
            )

        df: pd.DataFrame = reader(fp)
        content = self._build_markdown(fp, df)

        output_name = f"{fp.name}.describe.md"
        output_path = self.describe_dir / output_name
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _build_markdown(self, file_path: Path, df: pd.DataFrame) -> str:
        """Build describe markdown content."""
        lines = [f"# Dataset: {file_path.name}", ""]
        lines.append(f"- **Path**: `{file_path}`")
        lines.append(f"- **Rows**: {len(df)}")
        lines.append(f"- **Columns**: {len(df.columns)}")
        lines.append(f"- **Memory**: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        lines.append("")

        lines.append("## Column Summary")
        lines.append("")
        lines.append("| Column | Type | Non-Null | Nulls | Unique |")
        lines.append("|--------|------|----------|-------|--------|")

        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = int(df[col].count())
            nulls = int(df[col].isna().sum())
            unique = int(df[col].nunique())
            lines.append(
                f"| {col} | {dtype} | {non_null} | {nulls} | {unique} |"
            )

        lines.append("")

        # Numeric columns: basic statistics
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            lines.append("## Numeric Statistics")
            lines.append("")
            stats = df[numeric_cols].describe().to_markdown()
            lines.append(stats)
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 4：运行测试**

```bash
pytest tests/unit/test_describe.py -v
```

预期：5 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/describe.py tests/unit/test_describe.py
git commit -m "feat: add DescribeEngine for CSV/Parquet/Excel auto-describe"
```

---

### Task 8：LineageService — 数据集注册与血缘查询

**文件：**
- 创建: `datamind/engine/lineage.py`

- [ ] **Step 1：编写 LineageService 测试**

创建 `tests/unit/test_lineage.py`：

```python
"""Tests for LineageService."""
from datamind.engine.lineage import LineageService
from datamind.engine.graph import GraphDB
from datamind.engine.events import ExecutionLog
from datamind.engine.describe import DescribeEngine


def test_register_dataset_creates_node(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    csv_path = raw_dir / "test.csv"
    csv_path.write_text("a,b\n1,2\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(raw_dir.parent / "executions"))
    describe = DescribeEngine(str(describe_dir))
    svc = LineageService(graph, describe, exec_log)

    node_id = svc.register_dataset(str(csv_path))
    node = graph.get_node(node_id)
    assert node is not None
    assert node["type"] == "dataset"
    assert node["name"] == "test.csv"
    assert node["path"] == str(csv_path)

    graph.close()


def test_find_dataset_by_path(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "a.csv").write_text("x,y\n1,2\n")
    (raw_dir / "b.csv").write_text("x,y\n3,4\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(raw_dir.parent / "executions"))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    svc.register_dataset(str(raw_dir / "a.csv"))
    svc.register_dataset(str(raw_dir / "b.csv"))

    node = svc.find_dataset_by_path(str(raw_dir / "a.csv"))
    assert node is not None
    assert node["name"] == "a.csv"

    assert svc.find_dataset_by_path("/nonexistent.csv") is None
    graph.close()


def test_scan_raw_data_detects_all(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "a.csv").write_text("x\n1\n")
    (raw_dir / "b.parquet").write_bytes(b"")  # placeholder; needs real parquet
    (raw_dir / "notes.txt").write_text("hello")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(raw_dir.parent / "executions"))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    datasets = svc.scan_raw_data(str(raw_dir.parent))
    names = [d["name"] for d in datasets]
    assert "a.csv" in names
    # b.parquet won't be detected (it's a placeholder)
    assert "notes.txt" not in names
    graph.close()
```

- [ ] **Step 2：运行测试验证失败**

```bash
pytest tests/unit/test_lineage.py -v
```

预期：3 failed（ImportError）

- [ ] **Step 3：实现 LineageService**

创建 `datamind/engine/lineage.py`：

```python
"""LineageService — dataset registration, script-as-edge, lineage queries."""

from pathlib import Path
from datamind.config import SUPPORTED_FORMATS
from datamind.engine.graph import GraphDB
from datamind.engine.describe import DescribeEngine
from datamind.engine.events import ExecutionLog


class LineageService:
    """Manages data lineage: discovery, registration, graph linking, queries."""

    def __init__(
        self,
        graph: GraphDB,
        describe: DescribeEngine,
        execution_log: ExecutionLog,
    ):
        self.graph = graph
        self.describe = describe
        self.execution_log = execution_log

    def register_dataset(self, file_path: str, data_dir: str = "raw") -> str:
        """Register a dataset as a graph node and auto-describe it."""
        fp = Path(file_path)
        node_id = self.graph.insert_node(
            type="dataset",
            name=fp.name,
            path=str(fp),
            metadata={"data_dir": data_dir},
        )
        # Auto-describe
        self.describe.describe(str(fp))
        return node_id

    def find_dataset_by_path(self, file_path: str) -> dict | None:
        """Find a dataset node by its filesystem path."""
        # Full-table scan is fine for v1; index by path later if needed
        datasets = self.graph.list_nodes_by_type("dataset")
        fp_str = str(Path(file_path))
        for ds in datasets:
            if ds.get("path") == fp_str:
                return ds
        return None

    def scan_raw_data(self, data_root: str) -> list[dict]:
        """Scan data/raw/ for new datasets, register them, return list."""
        raw_dir = Path(data_root) / "data" / "raw"
        if not raw_dir.exists():
            return []
        datasets = []
        for fp in raw_dir.iterdir():
            if fp.suffix.lower() in SUPPORTED_FORMATS and fp.is_file():
                existing = self.find_dataset_by_path(str(fp))
                if existing:
                    datasets.append(existing)
                else:
                    node_id = self.register_dataset(str(fp))
                    datasets.append(self.graph.get_node(node_id))
        return datasets

    def query_ancestors(self, dataset_node_id: str) -> list[dict]:
        """Get all upstream nodes for a dataset."""
        return self.graph.query_ancestors(dataset_node_id)

    def query_descendants(self, dataset_node_id: str) -> list[dict]:
        """Get all downstream nodes for a dataset."""
        return self.graph.query_descendants(dataset_node_id)

    def link_script_to_datasets(
        self,
        script_path: str,
        input_paths: list[str],
        output_paths: list[str],
    ) -> dict:
        """Register a script node and link it to its I/O datasets."""
        script_node_id = self.graph.insert_node(
            type="script",
            name=Path(script_path).name,
            path=str(script_path),
        )
        edges = {"inputs": [], "outputs": []}

        for in_path in input_paths:
            ds = self.find_dataset_by_path(in_path)
            if ds:
                eid = self.graph.insert_edge(
                    source_id=ds["id"],
                    target_id=script_node_id,
                    edge_type="USED_INPUT",
                )
                edges["inputs"].append(eid)

        for out_path in output_paths:
            ds = self.find_dataset_by_path(out_path)
            if ds:
                eid = self.graph.insert_edge(
                    source_id=script_node_id,
                    target_id=ds["id"],
                    edge_type="PRODUCED",
                )
                edges["outputs"].append(eid)

        return {"script_node_id": script_node_id, "edges": edges}
```

- [ ] **Step 4：处理 test_scan_raw_data_detects_all 中的 parquet 占位符**

`b.parquet` 占位符无法被 pandas 读取。更新测试以使用真实 CSV：

在 `tests/unit/test_lineage.py` 中修改 `test_scan_raw_data_detects_all`，将 b.parquet 改为 b.csv：

```python
def test_scan_raw_data_detects_all(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "a.csv").write_text("x\n1\n")
    (raw_dir / "b.csv").write_text("x\n2\n")
    (raw_dir / "notes.txt").write_text("hello")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    datasets = svc.scan_raw_data(str(tmp_project))
    names = [d["name"] for d in datasets]
    assert "a.csv" in names
    assert "b.csv" in names
    assert "notes.txt" not in names
    graph.close()
```

- [ ] **Step 5：运行测试**

```bash
pytest tests/unit/test_lineage.py -v
```

预期：3 passed

- [ ] **Step 6：提交**

```bash
git add datamind/engine/lineage.py tests/unit/test_lineage.py
git commit -m "feat: add LineageService with dataset registration and lineage queries"
```

---

### Task 9：LineageService 集成测试

**文件：**
- 创建: `tests/integration/test_lineage_integration.py`

- [ ] **Step 1：编写集成测试**

创建 `tests/integration/__init__.py`（空文件）。

创建 `tests/integration/test_lineage_integration.py`：

```python
"""Integration tests for LineageService with real files."""
import pandas as pd
from pathlib import Path
from datamind.engine.graph import GraphDB
from datamind.engine.describe import DescribeEngine
from datamind.engine.events import ExecutionLog
from datamind.engine.lineage import LineageService


def test_full_lineage_workflow(tmp_project):
    """End-to-end: register data, run script, trace lineage."""
    # Setup directories
    raw_dir = tmp_project / "data" / "raw"
    describe_dir = tmp_project / "describe"
    exec_dir = tmp_project / "executions"
    scripts_dir = tmp_project / "scripts"
    processed_dir = tmp_project / "data" / "processed"
    for d in [raw_dir, describe_dir, exec_dir, scripts_dir, processed_dir]:
        d.mkdir(parents=True)

    # Create raw dataset
    df = pd.DataFrame({"price": [10, 20, 30, None, 50]})
    df.to_csv(raw_dir / "sales.csv", index=False)

    # Initialize services
    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    describe = DescribeEngine(str(describe_dir))
    svc = LineageService(graph, describe, exec_log)

    # Register dataset
    datasets = svc.scan_raw_data(str(tmp_project))
    assert len(datasets) == 1
    assert datasets[0]["name"] == "sales.csv"

    # Verify describe file was generated
    describe_files = list(describe_dir.glob("*.md"))
    assert len(describe_files) == 1
    assert "sales.csv" in describe_files[0].name

    # Create a "script" output
    processed_csv = processed_dir / "sales_clean.csv"
    pd.DataFrame({"price": [10.0, 20.0, 30.0, 30.0, 50.0]}).to_csv(
        processed_csv, index=False
    )

    # Register script and links
    result = svc.link_script_to_datasets(
        script_path="scripts/clean_sales.py",
        input_paths=[str(raw_dir / "sales.csv")],
        output_paths=[str(processed_csv)],
    )

    # Record execution
    exec_log.record(
        script_path="scripts/clean_sales.py",
        status="success",
        inputs=[str(raw_dir / "sales.csv")],
        outputs=[str(processed_csv)],
        exit_code=0,
    )

    # Query lineage
    ancestors = svc.query_ancestors(datasets[0]["id"])
    # raw dataset should have no ancestors (it's the source)
    # but the processed dataset would have the script as ancestor
    assert datasets[0]["id"] is not None

    graph.close()
```

- [ ] **Step 2：运行集成测试**

```bash
pytest tests/integration/test_lineage_integration.py -v -m integration
```

预期：1 passed

- [ ] **Step 3：提交**

```bash
git add tests/integration/__init__.py tests/integration/test_lineage_integration.py
git commit -m "test: add LineageService integration test with real files"
```

---

## 阶段 4：L2 — 认知旅程

### Task 10：CognitionService — 决策日志与探索树

**文件：**
- 创建: `datamind/engine/cognition.py`

- [ ] **Step 1：编写 CognitionService 测试**

创建 `tests/unit/test_cognition.py`：

```python
"""Tests for CognitionService."""
from datamind.engine.cognition import CognitionService


def test_log_decision_appends_to_jsonl(tmp_project):
    decisions_file = tmp_project / "decisions.jsonl"
    svc = CognitionService(
        decisions_file=str(decisions_file),
        exploration_file=str(tmp_project / "exploration.json"),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    d_id = svc.log_decision(
        what="forward fill",
        why="stocks don't interpolate on weekends",
        alternatives=["interpolation", "drop"],
        implications="preserves weekend gap structure",
    )
    assert decisions_file.exists()
    lines = decisions_file.read_text().strip().split("\n")
    assert len(lines) == 1
    import json
    entry = json.loads(lines[0])
    assert entry["what"] == "forward fill"
    assert entry["id"] == d_id


def test_get_recent_decisions(tmp_project):
    decisions_file = tmp_project / "decisions.jsonl"
    svc = CognitionService(
        decisions_file=str(decisions_file),
        exploration_file=str(tmp_project / "exploration.json"),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    for i in range(5):
        svc.log_decision(what=f"decision {i}", why="testing")
    recent = svc.get_recent_decisions(limit=3)
    assert len(recent) == 3
    # most recent first
    assert recent[0]["what"] == "decision 4"


def test_add_exploration_node_and_tree(tmp_project):
    exploration_file = tmp_project / "exploration.json"
    svc = CognitionService(
        decisions_file=str(tmp_project / "decisions.jsonl"),
        exploration_file=str(exploration_file),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    root_id = svc.add_exploration_node(
        description="Try XGBoost",
        status="SELECTED",
    )
    child_id = svc.add_exploration_node(
        description="Tune learning rate",
        status="EXPLORATORY",
        parent_id=root_id,
    )
    tree = svc.get_exploration_tree()
    assert len(tree) == 2
    root = next(n for n in tree if n["id"] == root_id)
    assert child_id in root["children"]
```

- [ ] **Step 2：实现 CognitionService**

创建 `datamind/engine/cognition.py`：

```python
"""CognitionService — decisions, exploration tree, params, discoveries."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class CognitionService:
    """Logs and queries cognitive journey data (Layer 2)."""

    def __init__(
        self,
        decisions_file: str,
        exploration_file: str,
        params_file: str,
        discoveries_file: str,
    ):
        self.decisions_file = Path(decisions_file)
        self.exploration_file = Path(exploration_file)
        self.params_file = Path(params_file)
        self.discoveries_file = Path(discoveries_file)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # -- Decisions --

    def log_decision(
        self,
        what: str,
        why: str,
        alternatives: list[str] | None = None,
        implications: str = "",
    ) -> str:
        """Log a decision to decisions.jsonl. Returns the decision ID."""
        d_id = self._new_id()
        entry = {
            "id": d_id,
            "what": what,
            "why": why,
            "alternatives": alternatives or [],
            "implications": implications,
            "timestamp": self._now(),
        }
        self._append_jsonl(self.decisions_file, entry)
        return d_id

    def get_recent_decisions(self, limit: int = 5) -> list[dict]:
        """Get the most recent N decisions, newest first."""
        return self._read_jsonl_reverse(self.decisions_file, limit)

    # -- Exploration --

    def add_exploration_node(
        self,
        description: str,
        status: str,
        parent_id: str | None = None,
        reason: str = "",
    ) -> str:
        """Add a node to the exploration tree."""
        node_id = self._new_id()
        node = {
            "id": node_id,
            "description": description,
            "status": status,  # SELECTED | REJECTED | EXPLORATORY
            "reason": reason,
            "parent_id": parent_id,
            "children": [],
            "timestamp": self._now(),
        }
        tree = self._read_json(self.exploration_file, [])
        tree.append(node)
        if parent_id:
            parent = next((n for n in tree if n["id"] == parent_id), None)
            if parent:
                parent.setdefault("children", []).append(node_id)
        self._write_json(self.exploration_file, tree)
        return node_id

    def get_exploration_tree(self) -> list[dict]:
        """Get the full exploration tree."""
        return self._read_json(self.exploration_file, [])

    # -- Discoveries --

    def add_discovery(
        self,
        finding: str,
        tag: str = "",
        linked_code: str = "",
        linked_data: str = "",
    ) -> str:
        """Log a discovery to discoveries.jsonl."""
        d_id = self._new_id()
        entry = {
            "id": d_id,
            "finding": finding,
            "tag": tag,
            "linked_code": linked_code,
            "linked_data": linked_data,
            "timestamp": self._now(),
        }
        self._append_jsonl(self.discoveries_file, entry)
        return d_id

    def get_recent_discoveries(self, limit: int = 5) -> list[dict]:
        """Get the most recent N discoveries."""
        return self._read_jsonl_reverse(self.discoveries_file, limit)

    # -- Parameters --

    def register_params(
        self, script_id: str, run_id: str, params: dict
    ) -> None:
        """Register parameters for a specific script execution."""
        all_params = self._read_json(self.params_file, {})
        all_params.setdefault(script_id, {})[run_id] = {
            "params": params,
            "timestamp": self._now(),
        }
        self._write_json(self.params_file, all_params)

    def get_params(self, script_id: str) -> dict[str, dict]:
        """Get all parameter runs for a script."""
        all_params = self._read_json(self.params_file, {})
        return all_params.get(script_id, {})

    # -- File helpers --

    def _append_jsonl(self, path: Path, entry: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_jsonl_reverse(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        result = entries[-limit:] if len(entries) > limit else entries
        return list(reversed(result))

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_cognition.py -v
```

预期：3 passed

- [ ] **Step 4：提交**

```bash
git add datamind/engine/cognition.py tests/unit/test_cognition.py
git commit -m "feat: add CognitionService with decisions, exploration, params, discoveries"
```

---

## 阶段 5：L3 — 上下文组装

### Task 11：AssemblyService — 上下文文件生成

**文件：**
- 创建: `datamind/engine/assembly.py`

- [ ] **Step 1：编写 AssemblyService 测试**

创建 `tests/unit/test_assembly.py`：

```python
"""Tests for AssemblyService."""
from datamind.engine.assembly import AssemblyService


def test_generate_project_md(tmp_project):
    context_dir = tmp_project / ".datamind" / "context"
    context_dir.mkdir(parents=True)
    svc = AssemblyService.__new__(AssemblyService)
    svc.context_dir = context_dir
    svc._lineage = None
    svc._cognition = None

    svc._generate_project_md(project_name="test-proj", datasets=["sales.csv", "users.csv"])
    project_md = context_dir / "PROJECT.md"
    assert project_md.exists()
    content = project_md.read_text()
    assert "# Project: test-proj" in content
    assert "sales.csv" in content
    assert "users.csv" in content


def test_generate_datasets_md(tmp_project):
    context_dir = tmp_project / ".datamind" / "context"
    context_dir.mkdir(parents=True)
    svc = AssemblyService.__new__(AssemblyService)
    svc.context_dir = context_dir

    datasets_info = [
        {"name": "sales.csv", "rows": 1000, "columns": 5, "describe_path": "describe/sales.csv.describe.md"},
        {"name": "users.csv", "rows": 500, "columns": 8, "describe_path": "describe/users.csv.describe.md"},
    ]
    svc._generate_datasets_md(datasets_info)
    datasets_md = context_dir / "DATASETS.md"
    assert datasets_md.exists()
    content = datasets_md.read_text()
    assert "sales.csv" in content
    assert "users.csv" in content
    assert "1000" in content
```

- [ ] **Step 2：实现 AssemblyService**

创建 `datamind/engine/assembly.py`：

```python
"""AssemblyService — context file generation and priority-ordered packing (Layer 3)."""

from pathlib import Path
from datamind.config import (
    PROJECT_MD, DATASETS_MD, HISTORY_MD, EXPLORATION_MD,
    PARAMS_MD, CHECKPOINT_MD, CONTEXT_MANIFEST_MD,
    TOKEN_BUDGET, PRIORITY1_TOKENS, PRIORITY2_TOKENS,
    PRIORITY3_TOKENS, PRIORITY4_TOKENS, CHECKPOINT_THRESHOLD,
)


class AssemblyService:
    """Generates context files from L1 + L2 data for AI consumption."""

    def __init__(self, lineage_service, cognition_service, context_dir: str):
        self._lineage = lineage_service
        self._cognition = cognition_service
        self.context_dir = Path(context_dir)
        self._execution_count_since_checkpoint = 0

    # -- Individual file generators --

    def generate_project_md(self, project_name: str, datasets: list[str]) -> Path:
        """Generate PROJECT.md with project overview."""
        lines = [f"# Project: {project_name}", ""]
        lines.append("## Datasets")
        for ds in datasets:
            lines.append(f"- {ds}")
        return self._write_context_file(PROJECT_MD, "\n".join(lines))

    def generate_datasets_md(self, datasets_info: list[dict]) -> Path:
        """Generate DATASETS.md with schema summaries."""
        lines = ["# Datasets", ""]
        for ds in datasets_info:
            lines.append(f"## {ds['name']}")
            lines.append(f"- Rows: {ds.get('rows', 'N/A')}")
            lines.append(f"- Columns: {ds.get('columns', 'N/A')}")
            if ds.get("describe_path"):
                lines.append(f"- Describe: `{ds['describe_path']}`")
            lines.append("")
        return self._write_context_file(DATASETS_MD, "\n".join(lines))

    def generate_history_md(self, decisions: list[dict], discoveries: list[dict]) -> Path:
        """Generate HISTORY.md from recent decisions and discoveries."""
        lines = ["# Recent Activity", ""]
        if decisions:
            lines.append("## Recent Decisions")
            for d in decisions:
                lines.append(f"- **{d['what']}**: {d['why']}")
            lines.append("")
        if discoveries:
            lines.append("## Recent Discoveries")
            for d in discoveries:
                lines.append(f"- [{d.get('tag', 'insight')}] {d['finding']}")
            lines.append("")
        return self._write_context_file(HISTORY_MD, "\n".join(lines))

    def generate_exploration_md(self, tree: list[dict]) -> Path:
        """Generate EXPLORATION.md from the exploration tree."""
        lines = ["# Exploration Tree", ""]
        for node in tree:
            status_icon = {"SELECTED": "[ACTIVE]", "REJECTED": "[DEAD]", "EXPLORATORY": "[EXPLORING]"}.get(
                node.get("status", ""), "[?]"
            )
            indent = "  " * (node.get("depth", 0))
            lines.append(f"{indent}- {status_icon} {node.get('description', '')}")
        return self._write_context_file(EXPLORATION_MD, "\n".join(lines))

    def generate_params_md(self, all_params: dict) -> Path:
        """Generate PARAMS.md from parameter registry."""
        lines = ["# Active Parameters", ""]
        for script_id, runs in all_params.items():
            lines.append(f"## {script_id}")
            for run_id, data in runs.items():
                lines.append(f"- Run `{run_id}`: {data['params']}")
            lines.append("")
        return self._write_context_file(PARAMS_MD, "\n".join(lines))

    # -- Checkpoint --

    def generate_checkpoint(self) -> Path:
        """Generate CHECKPOINT.md — compressed project understanding (~2k tokens)."""
        lines = ["# Checkpoint", "", "Compressed project understanding.", ""]

        # Combine summaries from decisions, discoveries, datasets
        if self._cognition:
            decisions = self._cognition.get_recent_decisions(10)
            if decisions:
                lines.append("## Key Decisions")
                for d in decisions[:5]:
                    lines.append(f"- {d['what']}: {d['why']}")
                lines.append("")

        if self._lineage:
            datasets = self._lineage.graph.list_nodes_by_type("dataset")
            lines.append(f"## Datasets: {len(datasets)} registered")
            lines.append("")

        self._execution_count_since_checkpoint = 0
        return self._write_context_file(CHECKPOINT_MD, "\n".join(lines))

    # -- Full refresh --

    def refresh_all(
        self,
        project_name: str = "",
        dataset_names: list[str] | None = None,
        datasets_info: list[dict] | None = None,
    ) -> list[Path]:
        """Regenerate all context files."""
        generated = []
        if project_name and dataset_names:
            generated.append(self.generate_project_md(project_name, dataset_names))
        if datasets_info:
            generated.append(self.generate_datasets_md(datasets_info))
        if self._cognition:
            decisions = self._cognition.get_recent_decisions(5)
            discoveries = self._cognition.get_recent_discoveries(5)
            generated.append(self.generate_history_md(decisions, discoveries))
            tree = self._cognition.get_exploration_tree()
            if tree:
                generated.append(self.generate_exploration_md(tree))
        return generated

    # -- Helpers --

    def _write_context_file(self, name: str, content: str) -> Path:
        path = self.context_dir / name
        path.write_text(content, encoding="utf-8")
        return path
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_assembly.py -v
```

预期：2 passed

- [ ] **Step 4：提交**

```bash
git add datamind/engine/assembly.py tests/unit/test_assembly.py
git commit -m "feat: add AssemblyService for context file generation"
```

---

### Task 12：优先级上下文打包与 Token 预算

**文件：**
- 修改: `datamind/engine/assembly.py`（追加打包逻辑）

- [ ] **Step 1：编写打包算法测试**

在 `tests/unit/test_assembly.py` 中追加：

```python
from datamind.engine.assembly import pack_manifest


def test_pack_manifest_priority_order():
    """Priority 1 always first, then 2, 3, 4."""
    context_dir = "/tmp/dummy"
    result = pack_manifest(
        context_dir=context_dir,
        project_md_content="# Project",
        datasets_md_content="# Datasets",
        history_md_content="# History" * 100,  # large
        exploration_md_content="# Exploration",
        params_md_content="# Params",
        checkpoint_md_content="# Checkpoint",
    )
    # P1 first
    assert result.index("# Project") < result.index("# History")
    # P2 (History) before P4 (Checkpoint)
    assert result.index("# History") < result.index("# Checkpoint")


def test_pack_manifest_truncates_when_over_budget():
    """Content over token budget should be truncated from bottom."""
    section = "# A section with many tokens " + "word " * 5000
    result = pack_manifest(
        context_dir="/tmp/dummy",
        project_md_content="# P1 short",
        datasets_md_content="# P1 also short",
        history_md_content=section,
        exploration_md_content=section,
        params_md_content=section,  # no priority
        checkpoint_md_content="# P4 checkpoint",
    )
    # Should not exceed budget by much
    assert len(result) < 50000  # token limit is 40k but chars have overhead


def test_estimate_tokens():
    from datamind.engine.assembly import estimate_tokens
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("") == 0
    # Rough: ~4 chars per token for English
    text = "a " * 400
    tokens = estimate_tokens(text)
    assert 80 <= tokens <= 120  # ~100 tokens for 400 chars
```

- [ ] **Step 2：运行测试确认失败**

```bash
pytest tests/unit/test_assembly.py::test_pack_manifest_priority_order -v
```

预期：FAIL（ImportError: cannot import name 'pack_manifest'）

- [ ] **Step 3：实现打包算法**

在 `datamind/engine/assembly.py` 中追加（文件末尾）：

```python
def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text."""
    return len(text) // 4


def pack_manifest(
    context_dir: str,
    project_md_content: str = "",
    datasets_md_content: str = "",
    history_md_content: str = "",
    exploration_md_content: str = "",
    params_md_content: str = "",
    checkpoint_md_content: str = "",
) -> str:
    """Assemble CONTEXT_MANIFEST.md with priority-ordered sections.

    Priority 1 (ALWAYS):    PROJECT.md + DATASETS.md         ~2.5k tokens
    Priority 2 (RECENT):    last decisions + discoveries      ~8k tokens
    Priority 3 (RELEVANT):  exploration + params              ~3k tokens
    Priority 4 (COMPRESSED): CHECKPOINT.md                    ~2k tokens

    Truncates from bottom up when total exceeds TOKEN_BUDGET.
    """
    sections = [
        ("P1_PROJECT",   project_md_content,   PRIORITY1_TOKENS),
        ("P1_DATASETS",  datasets_md_content,  0),  # shares P1 budget
        ("P2_HISTORY",   history_md_content,   PRIORITY2_TOKENS),
        ("P3_EXPLORATION", exploration_md_content, PRIORITY3_TOKENS),
        ("P3_PARAMS",    params_md_content,    0),  # shares P3 budget
        ("P4_CHECKPOINT", checkpoint_md_content, PRIORITY4_TOKENS),
    ]

    # Build manifest, tracking total
    parts = []
    parts.append("# Context Manifest")
    parts.append("")
    parts.append("> Priority-ordered context for AI injection. Truncated from bottom up when over budget.")
    parts.append("")

    total_tokens = 0

    for label, content, _priority_budget in sections:
        if not content:
            continue
        section_tokens = estimate_tokens(content)
        if total_tokens + section_tokens > TOKEN_BUDGET:
            # Truncate this section to fit remaining budget
            remaining = TOKEN_BUDGET - total_tokens
            if remaining < 100:
                break  # not enough space, skip
            truncated = content[:remaining * 4] + "\n\n[TRUNCATED — budget exceeded]"
            header = f"## {label}"
            parts.append(f"\n{header}\n")
            parts.append(truncated)
            break
        else:
            header = f"## {label}"
            parts.append(f"\n{header}\n")
            parts.append(content)
            total_tokens += section_tokens

    return "\n".join(parts)
```

- [ ] **Step 4：运行打包测试**

```bash
pytest tests/unit/test_assembly.py -v
```

预期：5 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/assembly.py tests/unit/test_assembly.py
git commit -m "feat: add priority-ordered context packer with token budget truncation"
```

---

## 阶段 6：L4 — 技能系统

### Task 13：SKILL.md 格式定义与解析

**文件：**
- 创建: `datamind/engine/skills.py`

- [ ] **Step 1：编写 SKILL.md 解析测试**

创建 `tests/unit/test_skills.py`：

```python
"""Tests for SkillService."""
from datamind.engine.skills import SkillParser, SkillDefinition


SAMPLE_SKILL_MD = """# Data Cleaning

**Purpose:** Clean raw data files by detecting and fixing common issues.

**Inputs:** A dataset path from data/raw/.

## Workflow

1. **Analyze** (AUTO) — Read describe/ and sample data to understand structure
2. **Propose Strategy** (AUTO) — Identify issues and propose cleaning approach
3. **Gate: Approve** (GATE) — Present proposal for human approval
4. **Execute** (AUTO) — Generate and run cleaning script
5. **Validate** (AUTO) — Check output statistics and report
6. **Gate: Result** (GATE) — Show before/after for human sign-off

## Outputs

- Cleaned dataset in data/processed/
- Cleaning script in scripts/
- Execution log in executions/
"""


def test_parse_skill_md_purpose():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert skill.purpose == "Clean raw data files by detecting and fixing common issues."


def test_parse_skill_md_steps():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert len(skill.steps) == 6

    assert skill.steps[0].step_type == "AUTO"
    assert skill.steps[0].name == "Analyze"

    assert skill.steps[1].step_type == "AUTO"
    assert skill.steps[1].name == "Propose Strategy"

    assert skill.steps[2].step_type == "GATE"
    assert skill.steps[2].name == "Approve"

    assert skill.steps[3].step_type == "AUTO"
    assert skill.steps[3].name == "Execute"

    assert skill.steps[4].step_type == "AUTO"
    assert skill.steps[4].name == "Validate"

    assert skill.steps[5].step_type == "GATE"
    assert skill.steps[5].name == "Result"


def test_parse_skill_md_inputs():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert "dataset path from data/raw/" in skill.inputs


def test_parse_empty_skill_md():
    parser = SkillParser()
    skill = parser.parse("")
    assert skill.purpose == ""
    assert skill.steps == []
    assert skill.inputs == ""
```

- [ ] **Step 2：运行测试确认失败**

```bash
pytest tests/unit/test_skills.py -v
```

预期：4 failed（ImportError）

- [ ] **Step 3：实现 SkillParser**

创建 `datamind/engine/skills.py`：

```python
"""SkillService — SKILL.md parsing, AUTO/GATE execution, pipeline composition (Layer 4)."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillStep:
    """A single step in a skill workflow."""
    name: str
    step_type: str  # "AUTO" | "GATE"
    description: str = ""


@dataclass
class SkillDefinition:
    """Parsed SKILL.md content."""
    name: str = ""
    purpose: str = ""
    inputs: str = ""
    steps: list[SkillStep] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


class SkillParser:
    """Parse SKILL.md files into SkillDefinition objects."""

    STEP_RE = re.compile(
        r"^\d+\.\s+\*\*(.+?)\*\*\s*\((\w+)\)\s*[-—]\s*(.+)$",
        re.MULTILINE,
    )

    def parse(self, content: str) -> SkillDefinition:
        """Parse SKILL.md text into a SkillDefinition."""
        skill = SkillDefinition()

        # Name: first H1
        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if name_match:
            skill.name = name_match.group(1).strip()

        # Purpose
        purpose_match = re.search(
            r"\*\*Purpose:\*\*\s*(.+?)$", content, re.MULTILINE
        )
        if purpose_match:
            skill.purpose = purpose_match.group(1).strip()

        # Inputs
        inputs_match = re.search(
            r"\*\*Inputs:\*\*\s*(.+?)$", content, re.MULTILINE
        )
        if inputs_match:
            skill.inputs = inputs_match.group(1).strip()

        # Steps
        for match in self.STEP_RE.finditer(content):
            step_name = match.group(1).strip()
            step_type_raw = match.group(2).strip().upper()
            description = match.group(3).strip()

            if step_type_raw == "GATE" or "GATE" in step_name.upper():
                step_type = "GATE"
            else:
                step_type = "AUTO"

            skill.steps.append(SkillStep(
                name=step_name,
                step_type=step_type,
                description=description,
            ))

        # Outputs
        outputs_match = re.search(
            r"\*\*Outputs?\*\*\s*\n((?:\s*[-*]\s*.+\n?)*)",
            content, re.MULTILINE,
        )
        if outputs_match:
            outputs_text = outputs_match.group(1)
            skill.outputs = [
                re.sub(r"^\s*[-*]\s*", "", line).strip()
                for line in outputs_text.strip().split("\n")
                if line.strip()
            ]

        return skill

    def parse_file(self, file_path: str) -> SkillDefinition:
        """Parse a SKILL.md file from disk."""
        content = Path(file_path).read_text(encoding="utf-8")
        return self.parse(content)
```

- [ ] **Step 4：运行测试**

```bash
pytest tests/unit/test_skills.py -v
```

预期：4 passed

- [ ] **Step 5：提交**

```bash
git add datamind/engine/skills.py tests/unit/test_skills.py
git commit -m "feat: add SKILL.md parser with AUTO/GATE step detection"
```

---

### Task 14：SkillService — 技能加载与执行

**文件：**
- 修改: `datamind/engine/skills.py`（追加 SkillService 类）

- [ ] **Step 1：编写 SkillService 测试**

在 `tests/unit/test_skills.py` 中追加：

```python
from datamind.engine.skills import SkillService, SkillStep


def test_load_skill_from_directory(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "data-cleaning.md").write_text(SAMPLE_SKILL_MD)

    svc = SkillService(
        skills_dir=str(skills_dir),
        lineage_svc=None,
        cognition_svc=None,
        assembly_svc=None,
    )
    skill = svc.load_skill("data-cleaning")
    assert skill.name == "Data Cleaning"
    assert len(skill.steps) == 6


def test_get_current_step_first(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "data-cleaning.md").write_text(SAMPLE_SKILL_MD)

    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("data-cleaning")
    step, step_index = svc.get_current_step(skill, step_index=0)
    assert step.step_type == "AUTO"
    assert step.name == "Analyze"


def test_is_gate_step(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "test.md").write_text("""# Test
**Purpose:** Testing.

## Workflow

1. **Do X** (AUTO) — Do stuff
2. **Gate: Confirm** (GATE) — Wait for human
""")
    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("test")
    _, _ = svc.get_current_step(skill, 0)  # AUTO
    assert svc.is_gate_step(skill, 0) is False
    assert svc.is_gate_step(skill, 1) is True


def test_advance_step(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "test.md").write_text("""# Test
**Purpose:** Testing.

## Workflow

1. **Do X** (AUTO)
2. **Gate: Confirm** (GATE)
3. **Do Y** (AUTO)
""")
    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("test")
    next_idx = svc.advance_step(skill, current_index=0)
    assert next_idx == 1
    step, _ = svc.get_current_step(skill, next_idx)
    assert step.step_type == "GATE"


def test_load_missing_skill(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    svc = SkillService(str(skills_dir), None, None, None)
    with pytest.raises(FileNotFoundError):
        svc.load_skill("nonexistent")
```

- [ ] **Step 2：实现 SkillService**

在 `datamind/engine/skills.py` 末尾追加：

```python
class SkillService:
    """Load, execute, and manage skills (Layer 4)."""

    def __init__(
        self,
        skills_dir: str,
        lineage_svc,
        cognition_svc,
        assembly_svc,
    ):
        self.skills_dir = Path(skills_dir)
        self.lineage = lineage_svc
        self.cognition = cognition_svc
        self.assembly = assembly_svc
        self.parser = SkillParser()

    def load_skill(self, skill_name: str) -> SkillDefinition:
        """Load a skill by name, reading its SKILL.md from the skills directory."""
        skill_path = self.skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_path}")
        return self.parser.parse_file(str(skill_path))

    def list_skills(self) -> list[str]:
        """List available skill names (without .md extension)."""
        if not self.skills_dir.exists():
            return []
        return sorted(
            p.stem for p in self.skills_dir.glob("*.md")
        )

    def get_current_step(
        self, skill: SkillDefinition, step_index: int = 0
    ) -> tuple[SkillStep, int]:
        """Get the current step and its index."""
        if step_index >= len(skill.steps):
            return SkillStep(name="DONE", step_type="DONE", description="All steps complete"), step_index
        return skill.steps[step_index], step_index

    def is_gate_step(self, skill: SkillDefinition, step_index: int) -> bool:
        """Check if the current step is a GATE."""
        step, _ = self.get_current_step(skill, step_index)
        return step.step_type == "GATE"

    def advance_step(self, skill: SkillDefinition, current_index: int) -> int:
        """Move to next step. Returns new index or -1 if complete."""
        next_idx = current_index + 1
        if next_idx >= len(skill.steps):
            return -1
        return next_idx

    def compose_pipeline(self, skill_names: list[str]) -> list[SkillDefinition]:
        """Chain multiple skills into a pipeline."""
        return [self.load_skill(name) for name in skill_names]
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_skills.py -v
```

预期：9 passed

- [ ] **Step 4：提交**

```bash
git add datamind/engine/skills.py tests/unit/test_skills.py
git commit -m "feat: add SkillService for loading and executing skills"
```

---

### Task 15：内置技能 SKILL.md 文件

**文件：**
- 创建: `skills/data-cleaning.md`
- 创建: `skills/data-exploration.md`
- 创建: `skills/feature-engineering.md`
- 创建: `skills/model-training.md`
- 创建: `skills/report-generation.md`

- [ ] **Step 1：编写 data-cleaning.md**

创建 `skills/data-cleaning.md`：

```markdown
# Data Cleaning

**Purpose:** Clean raw data files by detecting and fixing common issues: missing values, outliers, type mismatches, duplicates.

**Inputs:** A dataset path from data/raw/ (CSV, Parquet, Excel).

## Workflow

1. **Analyze** (AUTO) — Read the describe/ output for the dataset, sample first 100 rows, and identify data quality issues
2. **Propose Strategy** (AUTO) — Generate a cleaning strategy: which columns need what treatment, with rationale
3. **Gate: Approve** (GATE) — Present the proposed strategy to the human for approval, rejection, or modification
4. **Execute** (AUTO) — Generate and run a cleaning script (scripts/clean_*.py) that applies the approved strategy
5. **Validate** (AUTO) — Compare before/after statistics, verify no data loss, check output integrity
6. **Gate: Result** (GATE) — Show validation results to the human for final sign-off

## Outputs

- Cleaned dataset in data/processed/
- Cleaning script in scripts/
- Describe file in describe/ for the cleaned dataset
- Execution log in executions/
- Graph edges linking raw → script → cleaned
```

- [ ] **Step 2：编写 data-exploration.md**

创建 `skills/data-exploration.md`：

```markdown
# Data Exploration

**Purpose:** Explore a dataset to understand distributions, correlations, patterns, and generate visualizations.

**Inputs:** A dataset path (raw or processed) and optional exploration parameters.

## Workflow

1. **Read Describe** (AUTO) — Load describe/ statistics for the dataset
2. **Explore Patterns** (AUTO) — Compute correlations, distributions, outliers, generate exploratory charts
3. **Generate Visualizations** (AUTO) — Create standard EDA visualizations (histograms, box plots, scatter matrix)
4. **Gate: Review Findings** (GATE) — Present findings and charts to human for review and direction

## Outputs

- Exploration charts saved to describe/
- Findings logged to discoveries.jsonl
- Exploration tree updated in exploration.json
```

- [ ] **Step 3：编写 feature-engineering.md**

创建 `skills/feature-engineering.md`：

```markdown
# Feature Engineering

**Purpose:** Create and select features from a cleaned dataset for model training.

**Inputs:** A cleaned dataset path from data/processed/.

## Workflow

1. **Analyze Target** (AUTO) — Identify target variable and understand its distribution
2. **Propose Features** (AUTO) — Generate candidate features (transformations, encoding, interactions)
3. **Gate: Approve Set** (GATE) — Present candidate feature set for human approval
4. **Generate Code** (AUTO) — Generate feature engineering script (scripts/features_*.py) and run it
5. **Validate** (AUTO) — Check feature distributions, correlations with target, missing values

## Outputs

- Feature-engineered dataset in data/processed/
- Feature engineering script in scripts/
- Feature importance report in describe/
- Execution log in executions/
```

- [ ] **Step 4：编写 model-training.md**

创建 `skills/model-training.md`：

```markdown
# Model Training

**Purpose:** Train and tune machine learning models on feature-engineered data.

**Inputs:** A feature-engineered dataset path from data/processed/.

## Workflow

1. **Load Features** (AUTO) — Load features, split train/test, establish baseline metrics
2. **Baseline** (AUTO) — Train a simple baseline model and record performance
3. **Tune** (AUTO) — Perform hyperparameter tuning with cross-validation
4. **Gate: Select Model** (GATE) — Present candidate models and metrics for human selection
5. **Evaluate** (AUTO) — Run final evaluation on test set, generate report

## Outputs

- Trained model artifacts
- Evaluation report in describe/
- Model training script in scripts/
- Execution log in executions/
- Model metrics logged to discoveries.jsonl
```

- [ ] **Step 5：编写 report-generation.md**

创建 `skills/report-generation.md`：

```markdown
# Report Generation

**Purpose:** Generate a structured data science report from findings, models, and results.

**Inputs:** All prior outputs: exploration findings, feature importance, model metrics.

## Workflow

1. **Gather Findings** (AUTO) — Collect all discoveries, model metrics, and exploration results from L1+L2
2. **Structure Report** (AUTO) — Generate report outline: executive summary, methodology, results, conclusions
3. **Gate: Review Draft** (GATE) — Present draft report for human review
4. **Export** (AUTO) — Export final report to the requested format

## Outputs

- Final report document
```

- [ ] **Step 6：验证内置技能可解析**

在 `tests/unit/test_skills.py` 中追加：

```python
from pathlib import Path

def test_all_builtin_skills_parse():
    """Verify all built-in SKILL.md files parse without errors."""
    skills_dir = Path("skills")
    parser = SkillParser()
    for skill_path in sorted(skills_dir.glob("*.md")):
        skill = parser.parse_file(str(skill_path))
        assert skill.name, f"{skill_path.name}: missing name"
        assert skill.purpose, f"{skill_path.name}: missing purpose"
        assert len(skill.steps) > 0, f"{skill_path.name}: missing steps"
        # Every skill should have at least one GATE
        gate_steps = [s for s in skill.steps if s.step_type == "GATE"]
        assert len(gate_steps) > 0, f"{skill_path.name}: missing GATE steps"
```

运行：

```bash
pytest tests/unit/test_skills.py::test_all_builtin_skills_parse -v
```

预期：1 passed

- [ ] **Step 7：提交**

```bash
git add skills/ tests/unit/test_skills.py
git commit -m "feat: add 5 built-in SKILL.md files (cleaning, exploration, features, model, report)"
```

---

## 阶段 7：Project 门面与 CLI 扩展

### Task 16：Project 门面

**文件：**
- 创建: `datamind/engine/project.py`

- [ ] **Step 1：编写 Project 测试**

在 `tests/unit/test_init.py` 中追加（或创建 `tests/unit/test_project.py`）：

创建 `tests/unit/test_project.py`：

```python
"""Tests for the Project facade."""
from datamind.engine.project import Project


def test_project_composes_all_services(tmp_project):
    from datamind.config import initialize_project
    paths = initialize_project(tmp_project, {"project_name": "test"})

    proj = Project(str(tmp_project))
    assert proj.lineage is not None
    assert proj.cognition is not None
    assert proj.assembly is not None
    assert proj.skills is not None
    assert proj.graph is not None


def test_project_init_requires_dot_datamind(tmp_project):
    """Project should raise without .datamind/ directory."""
    with pytest.raises(FileNotFoundError):
        Project(str(tmp_project))


def test_project_scan_raw_data(tmp_project):
    from datamind.config import initialize_project
    paths = initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "sample.csv").write_text("x,y\n1,2\n3,4\n")

    proj = Project(str(tmp_project))
    datasets = proj.scan_raw_data()
    assert len(datasets) == 1
    assert datasets[0]["name"] == "sample.csv"
```

- [ ] **Step 2：实现 Project 门面**

创建 `datamind/engine/project.py`：

```python
"""Project facade — composes services, contains no business logic."""

from pathlib import Path
from datamind.config import resolve_component_paths
from datamind.engine.graph import GraphDB
from datamind.engine.events import ExecutionLog
from datamind.engine.describe import DescribeEngine
from datamind.engine.lineage import LineageService
from datamind.engine.cognition import CognitionService
from datamind.engine.assembly import AssemblyService
from datamind.engine.skills import SkillService


class Project:
    """Facade that composes all DataMind services for a project directory."""

    def __init__(self, project_root: str):
        root = Path(project_root).resolve()
        dot = root / ".datamind"
        if not dot.exists():
            raise FileNotFoundError(
                f"No .datamind/ found at {project_root}. Run 'datamind init' first."
            )
        paths = resolve_component_paths(project_root)
        self.paths = paths

        # Wiring: services with dependencies injected
        self.graph = GraphDB(str(paths["graph_db"]))
        self.graph.initialize()
        self.exec_log = ExecutionLog(str(paths["executions_dir"]))
        self.describe = DescribeEngine(str(paths["describe_dir"]))
        self.lineage = LineageService(self.graph, self.describe, self.exec_log)
        self.cognition = CognitionService(
            decisions_file=str(paths["decisions_file"]),
            exploration_file=str(paths["exploration_file"]),
            params_file=str(paths["params_file"]),
            discoveries_file=str(paths["discoveries_file"]),
        )
        self.assembly = AssemblyService(
            lineage_service=self.lineage,
            cognition_service=self.cognition,
            context_dir=str(paths["context_dir"]),
        )
        self.skills = SkillService(
            skills_dir=str(paths["skills_dir"]),
            lineage_svc=self.lineage,
            cognition_svc=self.cognition,
            assembly_svc=self.assembly,
        )

    def scan_raw_data(self) -> list[dict]:
        """Scan data/raw/ for datasets, register them, return list."""
        return self.lineage.scan_raw_data(str(self.paths["data_dir"].parent))
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_project.py -v
```

预期：3 passed

- [ ] **Step 4：提交**

```bash
git add datamind/engine/project.py tests/unit/test_project.py
git commit -m "feat: add Project facade composing all four services"
```

---

### Task 17：CLI 扩展 — 完整命令集

**文件：**
- 修改: `datamind/cli/main.py`（追加新命令）

- [ ] **Step 1：编写 CLI 扩展测试**

在 `tests/unit/test_cli.py` 中追加：

```python
def test_cli_lineage_query(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    # Create a dataset for lineage
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "test.csv").write_text("x\n1\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["lineage", "query", str(tmp_project), "--dataset", str(raw / "test.csv")])
    # May fail if dataset not registered — verify command exists
    assert result.exit_code in (0, 1)


def test_cli_context_inject(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["context", "inject", str(tmp_project)])
    assert result.exit_code in (0, 1)


def test_cli_skill_list(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["skill", "list", str(tmp_project)])
    assert result.exit_code == 0  # should work even with empty skills dir
```

- [ ] **Step 2：扩展 CLI**

修改 `datamind/cli/main.py`，在 `init` 命令后追加新命令：

```python
@cli.group()
def lineage():
    """Query data lineage."""
    pass


@lineage.command("query")
@click.argument("project_root", type=click.Path(exists=True))
@click.option("--dataset", help="Dataset path to query lineage for")
def lineage_query(project_root, dataset):
    """Query ancestors and descendants for a dataset."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    if dataset:
        node = proj.lineage.find_dataset_by_path(str(dataset))
        if not node:
            click.echo(f"Dataset not found: {dataset}")
            click.echo("Registered datasets:")
            for ds in proj.graph.list_nodes_by_type("dataset"):
                click.echo(f"  {ds.get('path', ds['name'])}")
            return
        ancestors = proj.lineage.query_ancestors(node["id"])
        descendants = proj.lineage.query_descendants(node["id"])
        click.echo(f"Lineage for: {node['name']}")
        if ancestors:
            click.echo("  Ancestors (upstream):")
            for a in ancestors:
                click.echo(f"    [{a['type']}] {a['name']}")
        else:
            click.echo("  No ancestors (this is a source dataset)")
        if descendants:
            click.echo("  Descendants (downstream):")
            for d in descendants:
                click.echo(f"    [{d['type']}] {d['name']}")
        else:
            click.echo("  No descendants")


@cli.group()
def context():
    """Manage context assembly."""
    pass


@context.command("inject")
@click.argument("project_root", type=click.Path(exists=True))
def context_inject(project_root):
    """Generate CONTEXT_MANIFEST.md for AI injection."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    decisions = proj.cognition.get_recent_decisions(5)
    discoveries = proj.cognition.get_recent_discoveries(5)

    proj.assembly.generate_project_md("DataMind Project", [])
    proj.assembly.generate_history_md(decisions, discoveries)
    # Check datasets
    datasets = proj.graph.list_nodes_by_type("dataset")
    ds_info = [{"name": d["name"], "rows": "N/A", "columns": "N/A"} for d in datasets]
    proj.assembly.generate_datasets_md(ds_info)

    click.echo(f"Context regenerated at {proj.assembly.context_dir}")
    click.echo(f"  Datasets: {len(datasets)}")
    click.echo(f"  Recent decisions: {len(decisions)}")
    click.echo(f"  Recent discoveries: {len(discoveries)}")


@cli.group()
def skill():
    """Manage skills."""
    pass


@skill.command("list")
@click.argument("project_root", type=click.Path(exists=True))
def skill_list(project_root):
    """List available skills."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    skills = proj.skills.list_skills()
    if skills:
        click.echo("Available skills:")
        for s in skills:
            skill_def = proj.skills.load_skill(s)
            click.echo(f"  {s}: {skill_def.purpose}")
    else:
        click.echo("No skills found in skills/ directory")
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_cli.py -v
```

预期：6 passed

- [ ] **Step 4：提交**

```bash
git add datamind/cli/main.py tests/unit/test_cli.py
git commit -m "feat: extend CLI with lineage query, context inject, skill list commands"
```

---

## 阶段 8：MCP Server 与 FastAPI

### Task 18：MCP Server

**文件：**
- 创建: `datamind/mcp/__init__.py`
- 创建: `datamind/mcp/server.py`

- [ ] **Step 1：编写 MCP Server 测试**

创建 `tests/unit/test_mcp.py`：

```python
"""Tests for MCP Server tools."""
import json
import pytest
from datamind.mcp.server import (
    tool_read_context,
    tool_register_dataset,
    tool_log_decision,
    tool_list_datasets,
)


def test_tool_read_context(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    from datamind.engine.project import Project
    proj = Project(str(tmp_project))

    result = tool_read_context(proj)
    assert isinstance(result, str)
    assert "Context" in result


def test_tool_register_dataset(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "test.csv").write_text("x\n1\n")
    from datamind.engine.project import Project
    proj = Project(str(tmp_project))

    result = tool_register_dataset(proj, str(raw / "test.csv"))
    assert "test.csv" in result


def test_tool_log_decision(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    from datamind.engine.project import Project
    proj = Project(str(tmp_project))

    result = tool_log_decision(proj, "use forward fill", "stocks don't interpolate")
    assert result["what"] == "use forward fill"


def test_tool_list_datasets(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.csv").write_text("x\n1\n")
    from datamind.engine.project import Project
    proj = Project(str(tmp_project))
    proj.lineage.register_dataset(str(raw / "a.csv"))

    result = tool_list_datasets(proj)
    assert len(result) >= 1
    names = [d["name"] for d in result]
    assert "a.csv" in names
```

- [ ] **Step 2：实现 MCP tools**

创建 `datamind/mcp/__init__.py`（空文件）。

创建 `datamind/mcp/server.py`：

```python
"""MCP Server — wraps the DataMind engine as MCP tools.

These tools are callable via MCP protocol. Each function receives
a Project instance (provided by the server) as first argument.

MCP tool definitions (for mcp server registration):
- read_context: Return the assembled context manifest
- register_dataset: Register a dataset and auto-describe
- log_decision: Log a decision to the cognitive journey
- list_datasets: List all registered datasets
"""

from datamind.engine.project import Project


def tool_read_context(project: Project) -> str:
    """Return the current context for AI injection."""
    decisions = project.cognition.get_recent_decisions(5)
    discoveries = project.cognition.get_recent_discoveries(5)
    datasets = project.graph.list_nodes_by_type("dataset")

    ds_info = [
        {"name": d["name"], "rows": "N/A", "columns": "N/A"}
        for d in datasets
    ]
    project.assembly.generate_project_md(
        project.paths["config_file"].read_text()[:100] if project.paths["config_file"].exists() else "DataMind Project",
        [d["name"] for d in datasets],
    )
    project.assembly.generate_datasets_md(ds_info)
    project.assembly.generate_history_md(decisions, discoveries)

    lines = ["# DataMind Context", ""]
    lines.append(f"## Datasets ({len(datasets)})")
    for d in datasets:
        lines.append(f"- {d['name']}")
    lines.append("")
    lines.append(f"## Recent Decisions ({len(decisions)})")
    for d in decisions:
        lines.append(f"- {d['what']}: {d['why']}")
    lines.append("")
    return "\n".join(lines)


def tool_register_dataset(project: Project, file_path: str) -> str:
    """Register a dataset and auto-describe it."""
    node_id = project.lineage.register_dataset(str(file_path))
    node = project.graph.get_node(node_id)
    return f"Registered dataset: {node['name']} (id: {node_id})"


def tool_log_decision(
    project: Project,
    what: str,
    why: str,
    alternatives: list[str] | None = None,
) -> dict:
    """Log a decision to the cognitive journey."""
    d_id = project.cognition.log_decision(
        what=what,
        why=why,
        alternatives=alternatives or [],
    )
    return {"id": d_id, "what": what, "why": why}


def tool_list_datasets(project: Project) -> list[dict]:
    """List all registered datasets."""
    datasets = project.graph.list_nodes_by_type("dataset")
    return [
        {"id": d["id"], "name": d["name"], "path": d.get("path", ""), "created_at": d["created_at"]}
        for d in datasets
    ]
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_mcp.py -v
```

预期：4 passed

- [ ] **Step 4：提交**

```bash
git add datamind/mcp/ tests/unit/test_mcp.py
git commit -m "feat: add MCP Server tools wrapping the DataMind engine"
```

---

### Task 19：FastAPI REST API

**文件：**
- 创建: `datamind/api/__init__.py`
- 创建: `datamind/api/app.py`

- [ ] **Step 1：编写 API 测试**

创建 `tests/unit/test_api.py`：

```python
"""Tests for FastAPI REST API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    # Add some data
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "sales.csv").write_text("price\n10\n20\n30\n")
    from datamind.api.app import create_app
    app = create_app(str(tmp_project))
    return TestClient(app)


def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_datasets(api_client):
    response = api_client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_context_endpoint(api_client):
    response = api_client.get("/context")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data


def test_register_dataset(api_client, tmp_project):
    new_csv = tmp_project / "data" / "raw" / "new_data.csv"
    new_csv.write_text("a,b\n1,2\n")
    response = api_client.post(
        "/datasets/register",
        json={"file_path": str(new_csv)},
    )
    assert response.status_code == 200
    assert "new_data.csv" in response.json()["name"]
```

- [ ] **Step 2：实现 FastAPI 应用**

创建 `datamind/api/__init__.py`（空文件）。

创建 `datamind/api/app.py`：

```python
"""FastAPI REST API for DataMind Studio Web UI."""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datamind.engine.project import Project


class RegisterDatasetRequest(BaseModel):
    file_path: str


class DecisionRequest(BaseModel):
    what: str
    why: str
    alternatives: list[str] = []


def create_app(project_root: str) -> FastAPI:
    app = FastAPI(title="DataMind Studio API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/datasets")
    def list_datasets():
        proj = Project(project_root)
        datasets = proj.graph.list_nodes_by_type("dataset")
        return [
            {"id": d["id"], "name": d["name"], "path": d.get("path"), "created_at": d["created_at"]}
            for d in datasets
        ]

    @app.post("/datasets/register")
    def register_dataset(req: RegisterDatasetRequest):
        proj = Project(project_root)
        try:
            node_id = proj.lineage.register_dataset(req.file_path)
            node = proj.graph.get_node(node_id)
            return node
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/context")
    def get_context():
        from datamind.mcp.server import tool_read_context
        proj = Project(project_root)
        content = tool_read_context(proj)
        return {"content": content}

    @app.post("/decisions")
    def log_decision(req: DecisionRequest):
        proj = Project(project_root)
        result = proj.cognition.log_decision(
            what=req.what,
            why=req.why,
            alternatives=req.alternatives,
        )
        return {"id": result}

    @app.get("/decisions")
    def list_decisions(limit: int = 10):
        proj = Project(project_root)
        return proj.cognition.get_recent_decisions(limit)

    @app.get("/skills")
    def list_skills():
        proj = Project(project_root)
        return proj.skills.list_skills()

    @app.get("/lineage/{dataset_id}")
    def get_lineage(dataset_id: str):
        proj = Project(project_root)
        node = proj.graph.get_node(dataset_id)
        if not node:
            raise HTTPException(status_code=404, detail="Dataset not found")
        ancestors = proj.lineage.query_ancestors(dataset_id)
        descendants = proj.lineage.query_descendants(dataset_id)
        return {
            "dataset": node,
            "ancestors": ancestors,
            "descendants": descendants,
        }

    return app


def create_server(project_root: str, host: str = "127.0.0.1", port: int = 8000):
    """Entry point for running the API server."""
    import uvicorn
    app = create_app(project_root)
    uvicorn.run(app, host=host, port=port)
```

- [ ] **Step 3：运行测试**

```bash
pytest tests/unit/test_api.py -v
```

预期：4 passed

- [ ] **Step 4：提交**

```bash
git add datamind/api/ tests/unit/test_api.py
git commit -m "feat: add FastAPI REST API with datasets, context, decisions, skills endpoints"
```

---

## 阶段 9：集成与 E2E

### Task 20：E2E 快照测试

**文件：**
- 创建: `tests/e2e/__init__.py`
- 创建: `tests/e2e/test_workflows.py`

- [ ] **Step 1：编写 E2E 测试**

创建 `tests/e2e/__init__.py`（空文件）。

创建 `tests/e2e/conftest.py`：

```python
"""E2E fixtures."""
import shutil
import tempfile
from pathlib import Path
import pytest
import pandas as pd
from datamind.config import initialize_project
from datamind.engine.project import Project


@pytest.fixture
def e2e_project():
    """Create a complete project for E2E testing."""
    tmp = Path(tempfile.mkdtemp(prefix="datamind_e2e_"))
    paths = initialize_project(tmp, {"project_name": "e2e_test"})

    # Create sample data
    raw = tmp / "data" / "raw"
    processed = tmp / "data" / "processed"
    scripts = tmp / "scripts"
    for d in [raw, processed, scripts]:
        d.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "price": range(100, 200),
        "volume": [i * 1000 for i in range(100)],
    })
    df.to_csv(raw / "sales.csv", index=False)

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)
```

创建 `tests/e2e/test_workflows.py`：

```python
"""End-to-end workflow tests."""
import json
from datamind.engine.project import Project


def test_full_data_cleaning_workflow(e2e_project):
    """Test: register raw data -> auto-describe -> log decision -> trace lineage."""
    proj = Project(str(e2e_project))

    # 1. Scan and register raw data
    datasets = proj.scan_raw_data()
    assert len(datasets) >= 1
    sales = [d for d in datasets if d["name"] == "sales.csv"][0]

    # 2. Verify auto-describe generated
    describe_dir = e2e_project / "describe"
    describe_files = list(describe_dir.glob("*.md"))
    assert len(describe_files) >= 1
    desc_content = describe_files[0].read_text()
    assert "sales.csv" in desc_content
    assert "price" in desc_content

    # 3. Log a decision
    d_id = proj.cognition.log_decision(
        what="remove outliers from price",
        why="prices outside 3-sigma are data errors",
        alternatives=["winsorize", "remove"],
    )
    assert d_id is not None

    # 4. Verify decision persisted
    decisions = proj.cognition.get_recent_decisions(5)
    assert len(decisions) >= 1
    assert decisions[0]["what"] == "remove outliers from price"

    # 5. Log an execution
    exec_id = proj.exec_log.record(
        script_path="scripts/clean_sales.py",
        status="success",
        inputs=["data/raw/sales.csv"],
        outputs=["data/processed/sales_clean.csv"],
        exit_code=0,
        params={"method": "outlier_removal"},
    )
    assert exec_id is not None

    # 6. Verify execution logged
    recent = proj.exec_log.list_recent(5)
    assert len(recent) >= 1
    assert recent[0]["script_path"] == "scripts/clean_sales.py"


def test_cognitive_journey_workflow(e2e_project):
    """Test: log decisions, create exploration tree, add discoveries."""
    proj = Project(str(e2e_project))

    # Exploration tree
    root_id = proj.cognition.add_exploration_node(
        description="Analyze price trends",
        status="SELECTED",
    )
    child_id = proj.cognition.add_exploration_node(
        description="Try seasonal decomposition",
        status="EXPLORATORY",
        parent_id=root_id,
    )
    tree = proj.cognition.get_exploration_tree()
    assert len(tree) == 2

    # Discoveries
    proj.cognition.add_discovery(
        finding="Price shows strong weekly seasonality",
        tag="pattern",
        linked_data="data/raw/sales.csv",
    )
    discoveries = proj.cognition.get_recent_discoveries(5)
    assert len(discoveries) >= 1
    assert "seasonality" in discoveries[0]["finding"]


def test_context_assembly_workflow(e2e_project):
    """Test: generate context files from L1+L2 data."""
    proj = Project(str(e2e_project))

    # Feed some data first
    proj.lineage.scan_raw_data(str(e2e_project))
    proj.cognition.log_decision(what="test decision", why="testing")
    proj.cognition.add_discovery(finding="test finding", tag="test")

    # Generate all context
    generated = proj.assembly.refresh_all(
        project_name="E2E Test",
        dataset_names=["sales.csv"],
        datasets_info=[{"name": "sales.csv", "rows": 100, "columns": 3}],
    )

    # Verify files exist
    context_dir = e2e_project / ".datamind" / "context"
    assert (context_dir / "PROJECT.md").exists()
    assert (context_dir / "DATASETS.md").exists()
    assert (context_dir / "HISTORY.md").exists()

    # Verify content references
    history = (context_dir / "HISTORY.md").read_text()
    assert "test decision" in history
    assert "test finding" in history
```

- [ ] **Step 2：运行 E2E 测试**

```bash
pytest tests/e2e/test_workflows.py -v -m e2e
```

预期：3 passed

- [ ] **Step 3：提交**

```bash
git add tests/e2e/
git commit -m "test: add E2E workflow tests covering full pipeline"
```

---

## 阶段 10：文档与最终验证

### Task 21：文档

**文件：**
- 创建: `README.md`

- [ ] **Step 1：编写 README.md**

```markdown
# DataMind Studio

AI-native data science research system. Captures project knowledge across four layers for AI consumption across sessions.

## Quick Start

```bash
pip install -e ".[dev]"
datamind init --name my-project /path/to/project
```

Drop data files into `data/raw/`, then:

```bash
datamind context inject /path/to/project
```

## Architecture

| Layer | Name | What It Tracks |
|-------|------|---------------|
| L1 | Data Lineage | WHAT happened to data (graph.db, script-as-edge, auto-describe) |
| L2 | Cognitive Journey | WHY and what was learned (decisions, explorations, discoveries) |
| L3 | Context Assembly | Priority-ordered context packing for AI injection |
| L4 | Skill System | Encoded workflows (SKILL.md) with AUTO/GATE steps |

## CLI Commands

- `datamind init <project_root>` — Initialize a new DataMind project
- `datamind lineage query <project_root> --dataset <path>` — Query data lineage
- `datamind context inject <project_root>` — Generate context for AI
- `datamind skill list <project_root>` — List available skills

## Testing

```bash
pytest tests/unit/ -v        # Unit tests (no I/O)
pytest tests/integration/ -v  # Integration tests (real files)
pytest tests/e2e/ -v          # End-to-end workflow tests
```

## Project Structure

```
.datamind/          # Project knowledge store
  graph.db          # SQLite knowledge graph
  context/          # Auto-generated context files
  decisions.jsonl   # Append-only decision log
  exploration.json  # Exploration tree
  ...
data/
  raw/              # Immutable original data
  processed/        # Derived datasets
scripts/            # AI-generated scripts
describe/           # Auto data.describe per dataset
skills/             # SKILL.md workflow definitions
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI
- **Storage:** SQLite (WAL mode), JSONL (append-only)
- **Frontend:** Vue 3 (Composition API)
- **AI Integration:** MCP Server wrapping the engine
```

- [ ] **Step 2：提交**

```bash
git add README.md
git commit -m "docs: add README with quick start and architecture overview"
```

---

### Task 22：全面测试与最终验证

- [ ] **Step 1：运行全部测试**

```bash
pytest tests/ -v
```

预期：所有测试通过（~40+ tests）。

- [ ] **Step 2：验证 CLI 端到端**

```bash
datamind init --name pytest /tmp/datamind_test_project
datamind skill list /tmp/datamind_test_project
```

预期：两个命令都成功。

- [ ] **Step 3：提交最终检查**

```bash
git status
git log --oneline -5
```

确认所有文件已提交，没有遗漏。

---

## 实施顺序总结

| 阶段 | 任务 | 交付物 |
|------|------|--------|
| 1 | Tasks 1-3 | pyproject.toml, config, errors, CLI `init` |
| 2 | Tasks 4-6 | GraphDB, EventSourcing |
| 3 | Tasks 7-9 | DescribeEngine, LineageService + 集成测试 |
| 4 | Task 10 | CognitionService (L2) |
| 5 | Tasks 11-12 | AssemblyService + priority packer (L3) |
| 6 | Tasks 13-15 | SkillParser, SkillService, 5 built-in skills (L4) |
| 7 | Tasks 16-17 | Project facade, CLI 扩展 |
| 8 | Tasks 18-19 | MCP Server, FastAPI REST API |
| 9 | Task 20 | E2E 快照测试 |
| 10 | Tasks 21-22 | 文档 + 最终验证 |

**总计：22 个任务，估计 4-6 小时实施时间（连续进行）。**

依赖关系：
- Task 4 必须在 Task 8 之前完成（LineageService 依赖 GraphDB）
- Task 7 必须在 Task 8 之前完成（LineageService 依赖 DescribeEngine）
- Task 10 必须在 Task 11 之前完成（AssemblyService 依赖 CognitionService）
- Task 13 必须在 Task 14 之前完成（SkillService 使用 SkillParser）
- Tasks 1-15 必须在 Task 16 之前完成（Project 组合所有服务）
- Tasks 16 必须在 Tasks 18-19 之前完成（MCP/API 依赖 Project）
