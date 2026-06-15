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
