"""LineageService — dataset registration, script-as-edge, lineage queries."""

from pathlib import Path
from datamind.config import SUPPORTED_FORMATS
from datamind.engine.graph import GraphDB
from datamind.engine.describe import DescribeEngine
from datamind.engine.events import ExecutionLog


class LineageService:
    """Manages data lineage: discovery, registration, graph linking, queries."""

    def __init__(self, graph: GraphDB, describe: DescribeEngine, execution_log: ExecutionLog):
        self.graph = graph
        self.describe = describe
        self.execution_log = execution_log

    def register_dataset(self, file_path: str, data_dir: str = "raw") -> str:
        """Register a dataset as a graph node and auto-describe it."""
        fp = Path(file_path)
        node_id = self.graph.insert_node(
            type="dataset", name=fp.name, path=str(fp), metadata={"data_dir": data_dir},
        )
        self.describe.describe(str(fp))
        return node_id

    def find_dataset_by_path(self, file_path: str) -> dict | None:
        """Find a dataset node by its filesystem path."""
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
        return self.graph.query_ancestors(dataset_node_id)

    def query_descendants(self, dataset_node_id: str) -> list[dict]:
        return self.graph.query_descendants(dataset_node_id)

    def link_script_to_datasets(self, script_path: str, input_paths: list[str], output_paths: list[str]) -> dict:
        """Register a script node and link it to its I/O datasets."""
        script_node_id = self.graph.insert_node(
            type="script", name=Path(script_path).name, path=str(script_path),
        )
        edges = {"inputs": [], "outputs": []}
        for in_path in input_paths:
            ds = self.find_dataset_by_path(in_path)
            if ds:
                eid = self.graph.insert_edge(source_id=ds["id"], target_id=script_node_id, edge_type="USED_INPUT")
                edges["inputs"].append(eid)
        for out_path in output_paths:
            ds = self.find_dataset_by_path(out_path)
            if ds:
                eid = self.graph.insert_edge(source_id=script_node_id, target_id=ds["id"], edge_type="PRODUCED")
                edges["outputs"].append(eid)
        return {"script_node_id": script_node_id, "edges": edges}
