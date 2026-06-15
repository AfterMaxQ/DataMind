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
