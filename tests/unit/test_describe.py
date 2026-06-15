"""Tests for the DescribeEngine."""
import pytest
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
