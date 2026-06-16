"""TDD tests for ToolRegistry and 7 data tools (datamind/engine/tools.py)."""
import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest
from datamind.engine.tools import (
    ToolRegistry,
    create_default_registry,
    describe_dataset,
    execute_script,
    generate_script,
    get_tool_schemas,
    list_files,
    read_csv,
    read_excel,
    read_parquet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_json_safe(obj):
    """Simulate JSON round-trip to verify serializability."""
    return json.loads(json.dumps(obj))


def _make_registry():
    """Create a fresh ToolRegistry."""
    return ToolRegistry()


# ===========================================================================
# Phase 1: ToolRegistry
# ===========================================================================

class TestToolRegistry:
    """Tests for ToolRegistry: register, get_definitions, execute, get."""

    def test_register_and_get_definitions(self):
        reg = _make_registry()
        reg.register(
            "hello",
            {"type": "function", "function": {"name": "hello"}},
            lambda name="world": {"result": f"hello {name}"},
        )
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "hello"

    def test_execute_known_tool(self):
        reg = _make_registry()
        reg.register(
            "add",
            {},
            lambda a=0, b=0: {"sum": a + b},
        )
        result = reg.execute("add", {"a": 3, "b": 4})
        assert result == {"sum": 7}

    def test_execute_unknown_tool_raises(self):
        reg = _make_registry()
        with pytest.raises(ValueError, match="Unknown tool"):
            reg.execute("no_such_tool", {})

    def test_get_known(self):
        reg = _make_registry()
        reg.register("t1", {}, lambda: {})
        schema, handler = reg.get("t1")
        assert schema == {}
        assert callable(handler)

    def test_get_unknown(self):
        reg = _make_registry()
        assert reg.get("not_there") is None


# ===========================================================================
# Phase 2: read_csv
# ===========================================================================

class TestReadCsv:
    """TDD for read_csv(path, nrows=10)."""

    def test_basic_csv_utf8(self, tmp_project):
        """Read a utf-8 CSV and verify structure."""

        csv_path = tmp_project / "sample.csv"
        csv_path.write_text("name,age,city\nAlice,30,NYC\nBob,25,SF\n", encoding="utf-8")

        result = read_csv(str(csv_path))
        result_js = _to_json_safe(result)

        assert result["file"] == str(csv_path)
        assert result["shape"] == [2, 3]
        assert result["columns"] == ["name", "age", "city"]
        assert len(result["sample"]) == 2
        assert result_js == result  # fully JSON-serializable

    def test_csv_with_nrows_limit(self, tmp_project):
        """nrows limits the sample returned."""

        csv_path = tmp_project / "big.csv"
        rows = "\n".join(f"x{i},y{i}" for i in range(50))
        csv_path.write_text(f"col1,col2\n{rows}\n", encoding="utf-8")

        result = read_csv(str(csv_path), nrows=5)
        assert len(result["sample"]) == 5
        assert result["shape"] == [50, 2]

    def test_csv_gbk_encoding(self, tmp_project):
        """Auto-detect GBK encoding."""

        csv_path = tmp_project / "gbk_sample.csv"
        # write a gbk-encoded file (Chinese characters)
        content = "中文,数据\nhello,world\n"
        csv_path.write_text(content, encoding="gbk")

        result = read_csv(str(csv_path))
        assert result["shape"] == [1, 2]
        assert "sample" in result

    def test_csv_dtypes_are_strings(self, tmp_project):
        """dtypes should be converted to strings for JSON serialization."""

        csv_path = tmp_project / "types.csv"
        csv_path.write_text("int_col,float_col,str_col\n1,2.5,hello\n", encoding="utf-8")

        result = read_csv(str(csv_path))
        for _, dtype in result["dtypes"].items():
            assert isinstance(dtype, str)

    def test_csv_nan_handling(self, tmp_project):
        """NaN values in sample data should be handled (converted to None for JSON)."""

        csv_path = tmp_project / "nan.csv"
        csv_path.write_text("a,b\n1,\n,2\n", encoding="utf-8")

        result = read_csv(str(csv_path))
        result_js = _to_json_safe(result)
        # Should survive JSON serialization without errors
        assert "sample" in result_js


# ===========================================================================
# Phase 3: read_parquet
# ===========================================================================

class TestReadParquet:
    """TDD for read_parquet(path, nrows=10)."""

    def test_basic_parquet(self, tmp_project):

        pq_path = tmp_project / "sample.parquet"
        df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        df.to_parquet(str(pq_path))

        result = read_parquet(str(pq_path))
        result_js = _to_json_safe(result)

        assert result["file"] == str(pq_path)
        assert result["shape"] == [3, 2]
        assert result["columns"] == ["x", "y"]
        assert len(result["sample"]) == 3
        assert result_js == result

    def test_parquet_nrows(self, tmp_project):

        pq_path = tmp_project / "big.parquet"
        df = pd.DataFrame({"i": range(100)})
        df.to_parquet(str(pq_path))

        result = read_parquet(str(pq_path), nrows=5)
        assert len(result["sample"]) == 5
        assert result["shape"] == [100, 1]

    def test_parquet_dtypes_are_strings(self, tmp_project):

        pq_path = tmp_project / "types.parquet"
        df = pd.DataFrame({"int_col": [1, 2], "float_col": [1.1, 2.2], "str_col": ["a", "b"]})
        df.to_parquet(str(pq_path))

        result = read_parquet(str(pq_path))
        for _, dtype in result["dtypes"].items():
            assert isinstance(dtype, str)


# ===========================================================================
# Phase 4: read_excel
# ===========================================================================

class TestReadExcel:
    """TDD for read_excel(path, nrows=10)."""

    def test_basic_excel(self, tmp_project):

        xlsx_path = tmp_project / "sample.xlsx"
        df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [90, 85]})
        df.to_excel(str(xlsx_path), index=False, engine="openpyxl")

        result = read_excel(str(xlsx_path))
        result_js = _to_json_safe(result)

        assert result["file"] == str(xlsx_path)
        assert result["shape"] == [2, 2]
        assert result["columns"] == ["name", "score"]
        assert len(result["sample"]) == 2
        assert result_js == result

    def test_excel_nrows(self, tmp_project):

        xlsx_path = tmp_project / "big.xlsx"
        df = pd.DataFrame({"i": range(50)})
        df.to_excel(str(xlsx_path), index=False, engine="openpyxl")

        result = read_excel(str(xlsx_path), nrows=5)
        assert len(result["sample"]) == 5
        assert result["shape"] == [50, 1]

    def test_excel_dtypes_are_strings(self, tmp_project):

        xlsx_path = tmp_project / "types.xlsx"
        df = pd.DataFrame({"x": [1, 2], "y": [1.5, 2.5], "z": ["p", "q"]})
        df.to_excel(str(xlsx_path), index=False, engine="openpyxl")

        result = read_excel(str(xlsx_path))
        for _, dtype in result["dtypes"].items():
            assert isinstance(dtype, str)


# ===========================================================================
# Phase 5: describe_dataset
# ===========================================================================

class TestDescribeDataset:
    """TDD for describe_dataset(path, describe_dir)."""

    def test_describe_csv(self, tmp_project):

        csv_path = tmp_project / "data" / "raw" / "sample.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")

        describe_dir = str(tmp_project / "describe")
        result = describe_dataset(str(csv_path), describe_dir)
        result_js = _to_json_safe(result)

        assert "describe_file" in result
        assert result["status"] == "success"
        assert os.path.exists(result["describe_file"])
        assert result_js == result

    def test_describe_file_not_found(self, tmp_project):

        describe_dir = str(tmp_project / "describe")
        result = describe_dataset(str(tmp_project / "missing.csv"), describe_dir)

        assert result["status"] == "error"
        assert "error" in result


# ===========================================================================
# Phase 6: generate_script
# ===========================================================================

class TestGenerateScript:
    """TDD for generate_script(template, params, output_path)."""

    def test_basic_template_replacement(self, tmp_project):

        template = "SELECT * FROM {{table}} WHERE date = '{{date}}'"
        params = {"table": "users", "date": "2024-01-01"}
        output = str(tmp_project / "query.sql")

        result = generate_script(template, params, output)
        result_js = _to_json_safe(result)

        assert result["status"] == "success"
        assert result["output_path"] == output
        assert os.path.exists(output)
        content = Path(output).read_text(encoding="utf-8")
        assert content == "SELECT * FROM users WHERE date = '2024-01-01'"
        assert result_js == result

    def test_template_missing_param_flagged(self, tmp_project):

        template = "SELECT * FROM {{table}} WHERE id = {{id}}"
        params = {"table": "users"}
        output = str(tmp_project / "partial.sql")

        result = generate_script(template, params, output)
        assert result["status"] == "success"
        # Verify that unresolved placeholders are removed from output
        content = Path(output).read_text(encoding="utf-8")
        assert "{{" not in content

    def test_template_no_placeholders(self, tmp_project):

        template = "SELECT 1"
        params = {}
        output = str(tmp_project / "static.sql")

        result = generate_script(template, params, output)
        assert result["status"] == "success"
        assert Path(output).read_text(encoding="utf-8") == "SELECT 1"


# ===========================================================================
# Phase 7: execute_script
# ===========================================================================

class TestExecuteScript:
    """TDD for execute_script(path, timeout=300)."""

    def test_execute_python_script(self, tmp_project):

        script = tmp_project / "hello.py"
        script.write_text('print("hello world")\n', encoding="utf-8")

        result = execute_script(str(script), timeout=30)
        result_js = _to_json_safe(result)

        assert result["status"] == "success"
        assert result["exit_code"] == 0
        assert "hello world" in result["stdout"]
        assert result_js == result

    def test_execute_script_with_error(self, tmp_project):

        script = tmp_project / "fail.py"
        script.write_text("import sys\nprint('oh no', file=sys.stderr)\nsys.exit(1)\n", encoding="utf-8")

        result = execute_script(str(script), timeout=30)

        assert result["status"] == "error"
        assert result["exit_code"] == 1

    def test_execute_script_timeout(self, tmp_project):

        script = tmp_project / "sleep.py"
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")

        result = execute_script(str(script), timeout=1)
        assert result["status"] == "timeout"

    def test_execute_script_runs_in_script_dir(self, tmp_project):

        script_dir = tmp_project / "scripts"
        script_dir.mkdir()
        script = script_dir / "whereami.py"
        script.write_text("import os\nprint(os.getcwd())\n", encoding="utf-8")

        result = execute_script(str(script), timeout=30)
        assert result["status"] == "success"
        # CWD should be the script's parent directory
        assert str(script_dir) in result["stdout"] or os.path.samefile(
            result["stdout"].strip(), str(script_dir)
        )

    def test_execute_large_output_truncation(self, tmp_project):

        script = tmp_project / "bigout.py"
        script.write_text("print('x' * 2_000_000)\n", encoding="utf-8")

        result = execute_script(str(script), timeout=30)
        assert result.get("output_truncated", False)
        # stdout should be at most ~1MB
        assert len(result["stdout"]) <= 1_100_000  # allow some slack


# ===========================================================================
# Phase 8: list_files
# ===========================================================================

class TestListFiles:
    """TDD for list_files(directory, pattern="*", recursive=False)."""

    def test_list_files_non_recursive(self, tmp_project):

        (tmp_project / "a.txt").write_text("", encoding="utf-8")
        (tmp_project / "b.txt").write_text("", encoding="utf-8")
        (tmp_project / "sub").mkdir()

        result = list_files(str(tmp_project))
        result_js = _to_json_safe(result)

        assert result["directory"] == str(tmp_project)
        assert len(result["files"]) >= 2  # a.txt, b.txt, plus maybe sub dir
        assert result_js == result
        # Check file structure
        for f in result["files"]:
            assert "name" in f
            assert "path" in f
            assert "size" in f
            assert "is_dir" in f

    def test_list_files_recursive(self, tmp_project):

        (tmp_project / "a.txt").write_text("", encoding="utf-8")
        sub = tmp_project / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("", encoding="utf-8")

        result = list_files(str(tmp_project), recursive=True)
        # Should find files in subdirectories too
        names = [f["name"] for f in result["files"]]
        assert "b.txt" in names

    def test_list_files_pattern_filter(self, tmp_project):

        (tmp_project / "a.csv").write_text("", encoding="utf-8")
        (tmp_project / "b.txt").write_text("", encoding="utf-8")

        result = list_files(str(tmp_project), pattern="*.csv")
        names = [f["name"] for f in result["files"]]
        assert "a.csv" in names
        assert "b.txt" not in names

    def test_list_files_empty_directory(self, tmp_project):

        result = list_files(str(tmp_project))
        assert result["directory"] == str(tmp_project)
        assert result["files"] == []


# ===========================================================================
# Phase 9: Integration — default registry
# ===========================================================================

class TestDefaultRegistry:
    """Verify that all 7 tools are registered in the default registry."""

    def test_all_tools_registered(self):

        reg = create_default_registry()
        defs = reg.get_definitions()
        names = sorted(d["function"]["name"] for d in defs)

        assert names == [
            "describe_dataset",
            "execute_script",
            "generate_script",
            "list_files",
            "read_csv",
            "read_excel",
            "read_parquet",
        ]

    def test_all_tools_executable(self, tmp_project):
        """Smoke test: register all tools and execute a simple one."""

        reg = create_default_registry()

        # Verify read_csv is executable
        csv_path = tmp_project / "smoke.csv"
        csv_path.write_text("x,y\n1,2\n", encoding="utf-8")
        result = reg.execute("read_csv", {"path": str(csv_path)})
        assert result["shape"] == [1, 2]

    def test_definitions_have_openai_format(self):

        reg = create_default_registry()
        for d in reg.get_definitions():
            assert d["type"] == "function"
            tool_def = d["function"]
            assert "name" in tool_def
            assert "description" in tool_def
            assert "parameters" in tool_def
            assert tool_def["parameters"]["type"] == "object"


# ===========================================================================
# Schema Tests
# ===========================================================================

class TestToolSchemas:
    """Verify each tool's schema is well-formed."""

    TOOL_NAMES = [
        "read_csv", "read_parquet", "read_excel",
        "describe_dataset", "generate_script", "execute_script", "list_files",
    ]

    def test_all_schemas_have_name(self):

        schemas = get_tool_schemas()
        for s in schemas:
            assert "function" in s
            assert "name" in s["function"]
            assert s["function"]["name"] in self.TOOL_NAMES

    def test_all_schemas_have_parameters(self):

        schemas = get_tool_schemas()
        for s in schemas:
            params = s["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
