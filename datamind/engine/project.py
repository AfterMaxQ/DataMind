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
        return self.lineage.scan_raw_data(str(self.paths["data_dir"].parent))
