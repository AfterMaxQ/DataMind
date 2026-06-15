"""Auto-describe engine for dataset files."""

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
        """Generate a describe/*.md for the given data file. Returns path to generated file."""
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

        df = reader(fp)
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
            lines.append(f"| {col} | {dtype} | {non_null} | {nulls} | {unique} |")

        lines.append("")

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            lines.append("## Numeric Statistics")
            lines.append("")
            stats = df[numeric_cols].describe().to_markdown()
            lines.append(stats)
            lines.append("")

        return "\n".join(lines)
