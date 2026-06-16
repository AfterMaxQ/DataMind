"""Tool system: ToolRegistry and 7 data tools for the LangGraph agent engine."""
import fnmatch
import os
import re
import subprocess
from pathlib import Path
from typing import Callable

import pandas as pd


# ===========================================================================
# Tool Registry
# ===========================================================================

class ToolRegistry:
    """Register and execute named tools with JSON-serializable schemas."""

    def __init__(self):
        self._tools: dict[str, tuple[dict, Callable[..., dict]]] = {}

    def register(self, name: str, schema: dict, handler: Callable[..., dict]) -> None:
        """Register a tool with its schema and handler function."""
        self._tools[name] = (schema, handler)

    def get_definitions(self) -> list[dict]:
        """Return all tool schemas (OpenAI function calling format)."""
        return [schema for schema, _ in self._tools.values()]

    def execute(self, name: str, args: dict) -> dict:
        """Execute a registered tool by name with the given arguments.

        Raises ValueError if the tool is not registered.
        """
        entry = self._tools.get(name)
        if entry is None:
            raise ValueError(f"Unknown tool: {name}")
        _, handler = entry
        return handler(**args)

    def get(self, name: str) -> tuple[dict, Callable[..., dict]] | None:
        """Return (schema, handler) for a tool, or None if not registered."""
        return self._tools.get(name)


# ===========================================================================
# Helper utilities
# ===========================================================================

# Encoding detection order for CSV files
_CSV_ENCODINGS = ["utf-8", "gbk", "gb2312", "latin-1", "cp1252"]


def _read_dataframe(path: str, nrows: int, reader_fn) -> dict:
    """Shared helper: read a dataframe (already loaded) and return tool result."""
    fp = Path(path)
    file_name = str(fp.resolve()) if fp.is_absolute() else str(Path.cwd() / fp)
    shape = [len(reader_fn), len(reader_fn.columns)]
    columns = reader_fn.columns.tolist()

    # Convert dtypes to strings for JSON serialization
    dtypes = {col: str(reader_fn[col].dtype) for col in reader_fn.columns}

    # Sample: first nrows rows. Replace NaN with None for JSON serialization.
    sample_df = reader_fn.head(nrows)
    sample = sample_df.where(sample_df.notna(), None).to_dict(orient="records")

    return {
        "file": os.path.abspath(str(fp)),
        "shape": shape,
        "columns": columns,
        "dtypes": dtypes,
        "sample": sample,
    }


# ===========================================================================
# Phase 2: read_csv
# ===========================================================================

def read_csv(path: str, nrows: int = 10) -> dict:
    """Read a CSV file with auto-encoding detection.

    Returns:
        dict with keys: file, shape, columns, dtypes, sample
    """
    last_error = None
    for enc in _CSV_ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc, nrows=None)
            result = _read_dataframe(path, nrows, df)
            return result
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    raise ValueError(f"Failed to decode CSV with any encoding: {last_error}")


# ===========================================================================
# Phase 3: read_parquet
# ===========================================================================

def read_parquet(path: str, nrows: int = 10) -> dict:
    """Read a Parquet file.

    Returns:
        dict with keys: file, shape, columns, dtypes, sample
    """
    df = pd.read_parquet(path)
    return _read_dataframe(path, nrows, df)


# ===========================================================================
# Phase 4: read_excel
# ===========================================================================

def read_excel(path: str, nrows: int = 10) -> dict:
    """Read an Excel file using the openpyxl engine.

    Returns:
        dict with keys: file, shape, columns, dtypes, sample
    """
    df = pd.read_excel(path, engine="openpyxl")
    return _read_dataframe(path, nrows, df)


# ===========================================================================
# Phase 5: describe_dataset
# ===========================================================================

def describe_dataset(path: str, describe_dir: str) -> dict:
    """Generate a dataset description markdown file using DescribeEngine.

    Lazily imports DescribeEngine to avoid circular imports.

    Returns:
        dict with keys: describe_file, status
    """
    try:
        from datamind.engine.describe import DescribeEngine

        os.makedirs(describe_dir, exist_ok=True)
        engine = DescribeEngine(describe_dir)
        output_path = engine.describe(path)
        return {
            "describe_file": str(output_path),
            "status": "success",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# ===========================================================================
# Phase 6: generate_script
# ===========================================================================

def generate_script(template: str, params: dict, output_path: str) -> dict:
    """Generate a script from a template with {{var}} placeholders.

    Args:
        template: Template string with {{var}} placeholders.
        params: Dict mapping variable names to replacement values.
        output_path: Path to write the generated script.

    Returns:
        dict with keys: status, output_path
    """
    content = template
    for key, value in params.items():
        content = content.replace("{{%s}}" % key, str(value))
    # Replace any remaining unreplaced placeholders with empty string
    content = re.sub(r"\{\{.*?\}\}", "", content)
    Path(output_path).write_text(content, encoding="utf-8")
    return {
        "status": "success",
        "output_path": str(output_path),
    }


# ===========================================================================
# Phase 7: execute_script
# ===========================================================================

# Maximum output size (1 MB)
_MAX_OUTPUT_BYTES = 1 * 1024 * 1024


def execute_script(path: str, timeout: int = 300) -> dict:
    """Execute a script in a subprocess sandbox.

    The script runs in its parent directory. stdout/stderr are captured and
    truncated at 1MB to prevent memory exhaustion.

    Args:
        path: Path to the script file.
        timeout: Maximum execution time in seconds.

    Returns:
        dict with keys: status, exit_code, stdout, stderr, output_truncated
    """
    script_path = Path(path).resolve()
    cwd = script_path.parent

    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
        stdout_raw = result.stdout or ""
        stderr_raw = result.stderr or ""

        output_truncated = (
            len(stdout_raw.encode("utf-8", errors="replace")) > _MAX_OUTPUT_BYTES
            or len(stderr_raw.encode("utf-8", errors="replace")) > _MAX_OUTPUT_BYTES
        )

        # Truncate to ~1MB
        stdout_enc = stdout_raw.encode("utf-8", errors="replace")
        stderr_enc = stderr_raw.encode("utf-8", errors="replace")
        stdout = stdout_enc[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        stderr = stderr_enc[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")

        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": output_truncated,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Script timed out after %d seconds" % timeout,
            "output_truncated": False,
        }


# ===========================================================================
# Phase 8: list_files
# ===========================================================================

def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> dict:
    """List files in a directory, optionally filtering by pattern.

    Args:
        directory: Directory path to list.
        pattern: fnmatch pattern to filter entries (default "*").
        recursive: If True, recurse into subdirectories.

    Returns:
        dict with keys: files (list of {name, path, size, is_dir}), directory
    """
    dir_path = Path(directory).resolve()
    entries = []

    if recursive:
        glob_iter = dir_path.rglob(pattern)
    else:
        glob_iter = dir_path.glob(pattern)

    for entry in sorted(glob_iter, key=lambda p: (not p.is_dir(), p.name.lower())):
        try:
            size = entry.stat().st_size if not entry.is_dir() else 0
        except OSError:
            size = 0
        entries.append({
            "name": entry.name,
            "path": str(entry),
            "size": size,
            "is_dir": entry.is_dir(),
        })

    return {
        "files": entries,
        "directory": str(dir_path),
    }


# ===========================================================================
# Phase 9: Default registry and tool schemas
# ===========================================================================

def get_tool_schemas() -> list[dict]:
    """Return the schema definitions for all 7 tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_csv",
                "description": "Read a CSV file with auto-encoding detection. Returns column names, dtypes, shape, and a sample of the first rows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the CSV file."},
                        "nrows": {"type": "integer", "description": "Number of sample rows to return.", "default": 10},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_parquet",
                "description": "Read a Parquet file. Returns column names, dtypes, shape, and a sample of the first rows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the Parquet file."},
                        "nrows": {"type": "integer", "description": "Number of sample rows to return.", "default": 10},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_excel",
                "description": "Read an Excel file (.xlsx) using the openpyxl engine. Returns column names, dtypes, shape, and a sample of the first rows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the Excel file."},
                        "nrows": {"type": "integer", "description": "Number of sample rows to return.", "default": 10},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "describe_dataset",
                "description": "Generate a comprehensive dataset description markdown file using the describe engine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the data file."},
                        "describe_dir": {"type": "string", "description": "Directory to write the describe markdown file."},
                    },
                    "required": ["path", "describe_dir"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_script",
                "description": "Generate a script file from a template with {{var}} placeholders replaced by parameter values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template": {"type": "string", "description": "Template string with {{var}} placeholders."},
                        "params": {"type": "object", "description": "Dict mapping variable names to replacement values."},
                        "output_path": {"type": "string", "description": "Path to write the generated script."},
                    },
                    "required": ["template", "params", "output_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_script",
                "description": "Execute a Python script in a subprocess sandbox. Returns exit code, stdout, and stderr. Output is truncated at 1MB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the script file."},
                        "timeout": {"type": "integer", "description": "Maximum execution time in seconds.", "default": 300},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory, optionally filtering by glob pattern and recursing into subdirectories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path to list."},
                        "pattern": {"type": "string", "description": "fnmatch pattern to filter entries.", "default": "*"},
                        "recursive": {"type": "boolean", "description": "Recurse into subdirectories.", "default": False},
                    },
                    "required": ["directory"],
                },
            },
        },
    ]


_HANDLERS = {
    "read_csv": read_csv,
    "read_parquet": read_parquet,
    "read_excel": read_excel,
    "describe_dataset": describe_dataset,
    "generate_script": generate_script,
    "execute_script": execute_script,
    "list_files": list_files,
}


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry with all 7 data tools pre-registered."""
    reg = ToolRegistry()
    for schema in get_tool_schemas():
        name = schema["function"]["name"]
        reg.register(name, schema, _HANDLERS[name])
    return reg
