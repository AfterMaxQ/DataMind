"""Project facade — composes services, contains no business logic."""

import logging
from pathlib import Path
from datamind.config import resolve_component_paths, load_llm_config
from datamind.engine.graph import GraphDB
from datamind.engine.events import ExecutionLog
from datamind.engine.describe import DescribeEngine
from datamind.engine.lineage import LineageService
from datamind.engine.cognition import CognitionService
from datamind.engine.assembly import AssemblyService
from datamind.engine.skills import SkillService
from datamind.engine.llm import OpenAIClient, OllamaClient
from datamind.engine.prompt import TemplateManager
from datamind.engine.usage import UsageTracker

_log = logging.getLogger(__name__)


def _create_llm_client(config: dict):
    """Create an LLM client (OpenAI, Ollama, or DeepSeek) from a config dict."""
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o")
    api_key = config.get("api_key") or ""
    api_base = config.get("api_base", "https://api.openai.com/v1")
    max_retries = config.get("max_retries", 3)

    if provider == "ollama":
        return OllamaClient(model=model, api_url=api_base)

    if provider == "deepseek":
        api_base = config.get("api_base", "https://api.deepseek.com/v1")

    return OpenAIClient(
        api_key=api_key,
        model=model,
        api_url=api_base,
        max_retries=max_retries,
    )


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

        # --- Core services (v1) ---
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

        # --- v2 engine services ---
        try:
            llm_config = load_llm_config(str(paths["config_file"]))
            self.llm_client = _create_llm_client(llm_config)
        except Exception as exc:
            _log.warning("Failed to create LLM client: %s. Using defaults.", exc)
            self.llm_client = OpenAIClient(
                api_key="",
                model="gpt-4o",
            )

        self.prompt_manager = TemplateManager(str(paths.get("prompts_dir", root / "prompts")))
        self.usage_tracker = UsageTracker()

    def scan_raw_data(self) -> list[dict]:
        return self.lineage.scan_raw_data(str(self.paths["data_dir"].parent))

    def create_agent(self) -> "DataMindAgent":
        from datamind.engine.agent import DataMindAgent
        from datamind.engine.tools import create_default_registry
        return DataMindAgent(
            llm_client=self.llm_client,
            prompt_manager=self.prompt_manager,
            usage_tracker=self.usage_tracker,
            lineage_service=self.lineage,
            cognition_service=self.cognition,
            assembly_service=self.assembly,
            tool_registry=create_default_registry(),
        )
