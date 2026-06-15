"""E2E fixtures."""
import shutil
import tempfile
from pathlib import Path
import pytest
import pandas as pd
from datamind.config import initialize_project


@pytest.fixture
def e2e_project():
    tmp = Path(tempfile.mkdtemp(prefix="datamind_e2e_"))
    initialize_project(tmp, {"project_name": "e2e_test"})
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
