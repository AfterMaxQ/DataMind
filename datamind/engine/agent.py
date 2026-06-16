"""DataMindAgent — the agent execution loop that ties together all v2 services.

Provides:
- :class:`AgentEvent` — base class for agent events
- :class:`AgentResponse` — AUTO phase completed successfully
- :class:`WaitForApproval` — GATE phase requires human approval
- :class:`AgentError` — error occurred during execution
- :class:`SkillComplete` — all phases completed
- :class:`DataMindAgent` — Context -> Prompt -> LLM -> Tools -> Record -> Repeat
"""

from dataclasses import dataclass, field

from datamind.engine.llm import LLMResponse
from datamind.engine.skill_state import SkillStateMachine


# ---------------------------------------------------------------------------
# Agent event types
# ---------------------------------------------------------------------------


class AgentEvent:
    """Base class for agent events returned by :meth:`DataMindAgent.run`."""


@dataclass
class AgentResponse(AgentEvent):
    """AUTO phase completed successfully.

    Attributes:
        content: The final text response from the LLM.
        tool_calls: All tool calls executed during this phase.
        usage: Token usage dict for the final LLM call.
        phase_id: The id of the AUTO phase that completed.
    """

    content: str
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    phase_id: str = ""


@dataclass
class WaitForApproval(AgentEvent):
    """GATE phase requires human approval before continuing.

    Attributes:
        phase_id: The id of the GATE phase awaiting approval.
        phase_name: Human-readable name of the GATE phase.
        context_message: Description of what decision is needed.
    """

    phase_id: str
    phase_name: str
    context_message: str = "awaiting decision"


@dataclass
class AgentError(AgentEvent):
    """Error occurred during agent execution.

    Attributes:
        error_message: Description of the error.
    """

    error_message: str


@dataclass
class SkillComplete(AgentEvent):
    """All phases in the workflow have completed.

    Attributes:
        result: Final result string (e.g. ``"pass"``).
        usage: Aggregated usage summary from the UsageTracker.
    """

    result: str
    usage: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DataMindAgent
# ---------------------------------------------------------------------------


class DataMindAgent:
    """Agent execution loop: Context -> Prompt -> LLM -> Tools -> Record -> Repeat.

    Drives a :class:`~datamind.engine.skill_state.SkillStateMachine` through its
    phases.  AUTO phases are processed by the LLM; GATE phases pause execution
    until :meth:`approve_gate` is called.

    Parameters:
        llm_client:
            Any object with a ``chat(messages, tools=None)`` method returning
            an :class:`~datamind.engine.llm.LLMResponse`.
        prompt_manager:
            A :class:`~datamind.engine.prompt.TemplateManager` with a
            ``render(name, variables)`` method.
        usage_tracker:
            A :class:`~datamind.engine.usage.UsageTracker` with a
            ``record(prompt_tokens, completion_tokens, model)`` method.
        lineage_service:
            Optional lineage service for recording decisions.
        cognition_service:
            Optional cognition service for recording decisions.
        assembly_service:
            Optional assembly service for context assembly.
        tool_registry:
            Optional :class:`~datamind.engine.tools.ToolRegistry` for tool
            definition lookup and execution.
    """

    def __init__(
        self,
        llm_client,
        prompt_manager,
        usage_tracker,
        lineage_service=None,
        cognition_service=None,
        assembly_service=None,
        tool_registry=None,
    ):
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager
        self.usage_tracker = usage_tracker
        self.lineage_service = lineage_service
        self.cognition_service = cognition_service
        self.assembly_service = assembly_service
        self._tool_registry = tool_registry
        self._state_machine: SkillStateMachine | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        state_machine: SkillStateMachine,
        user_input: str | None = None,
    ) -> AgentEvent:
        """Execute until an AUTO phase completes or a GATE phase pauses.

        If multiple AUTO phases are consecutive, all are processed in one call.
        Execution pauses at the first GATE phase encountered.

        Args:
            state_machine: The skill state machine to drive.
            user_input: Optional initial user message appended after the system
                prompt for the first AUTO phase.

        Returns:
            An :class:`AgentEvent` subclass describing what happened.
        """
        self._state_machine = state_machine
        return self._continue(user_input)

    def approve_gate(self, decision: dict) -> AgentEvent:
        """Approve the current GATE phase and continue execution.

        Calls
        :meth:`~datamind.engine.skill_state.SkillStateMachine.approve_gate`
        on the current phase, then resumes the execution loop so that
        subsequent AUTO phases are processed until the next GATE or workflow
        completion.

        Args:
            decision: Arbitrary dict capturing the human decision (serialized
                as a JSON artifact on the phase).

        Returns:
            An :class:`AgentEvent` subclass describing what happened next.
        """
        if self._state_machine is None:
            return AgentError("No active state machine")

        current = self._state_machine.get_current_phase()
        self._state_machine.approve_gate(current.id, decision)
        return self._continue()

    # ------------------------------------------------------------------
    # Internal: main loop
    # ------------------------------------------------------------------

    def _continue(self, user_input: str | None = None) -> AgentEvent:
        """Core loop: process phases until GATE pause or workflow completion."""
        sm = self._state_machine
        if sm is None:
            return AgentError("No active state machine")

        while True:
            # Check if the workflow is already complete
            if sm.state.result is not None:
                return SkillComplete(
                    result=sm.state.result,
                    usage=self.usage_tracker.export(),
                )

            phase = sm.get_current_phase()

            if phase.type == "GATE":
                return WaitForApproval(
                    phase_id=phase.id,
                    phase_name=phase.name,
                    context_message="awaiting decision",
                )

            # AUTO phase
            try:
                result = self._process_auto_phase(phase, user_input)
                if isinstance(result, AgentError):
                    return result
                # user_input only applies to the first phase in a run() call
                user_input = None
            except Exception as exc:
                return AgentError(str(exc))

    # ------------------------------------------------------------------
    # Internal: AUTO phase processing
    # ------------------------------------------------------------------

    def _process_auto_phase(self, phase, user_input: str | None = None) -> AgentEvent:
        """Run the LLM pipeline for a single AUTO phase.

        1. Assemble context from prior completed phases.
        2. Render the system prompt.
        3. Call the LLM (with optional user_input).
        4. Execute tool calls in a loop (max 5 tool turns).
        5. Record usage.
        6. Complete the phase and advance.
        """
        sm = self._state_machine

        # 1. Assemble context
        context = self._assemble_context(sm)

        # 2. Render prompt
        prompt = self.prompt_manager.render("data-scientist", {
            "context": context,
            "skills": "",
        })

        # 3. Build messages
        messages: list[dict] = [{"role": "system", "content": prompt}]
        if user_input:
            messages.append({"role": "user", "content": user_input})

        # 4. Initial LLM call
        tool_defs = self._get_tool_defs()
        response = self.llm_client.chat(messages=messages, tools=tool_defs)

        # 5. Tool call loop (max 5 tool turns)
        all_tool_calls: list[dict] = []
        tool_turns = 0

        while response.tool_calls and tool_turns < 5:
            all_tool_calls.extend(response.tool_calls)

            # Append assistant message with tool calls
            assistant_msg = {"role": "assistant", "content": response.content or ""}
            assistant_msg["tool_calls"] = self._format_tool_calls_for_message(response.tool_calls)
            messages.append(assistant_msg)

            # Execute tools and append results
            tool_results = self._execute_tools(response.tool_calls)
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("id", ""),
                    "content": tr.get("content", ""),
                })

            response = self.llm_client.chat(messages=messages, tools=tool_defs)
            tool_turns += 1

        # 6. Record usage
        if response.usage:
            self.usage_tracker.record(
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
                model=response.model or "unknown",
            )

        # 7. Record decision (if services available)
        self._record_decision(phase, response)

        # 8. Complete the phase
        sm.complete_phase(phase.id)

        return AgentResponse(
            content=response.content,
            tool_calls=all_tool_calls,
            usage=response.usage,
            phase_id=phase.id,
        )

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _assemble_context(self, sm: SkillStateMachine) -> str:
        """Build a context string from active (completed) phase artifacts."""
        artifacts = sm.get_active_artifacts()
        if not artifacts:
            return "No prior context available."
        return "Prior artifacts:\n" + "\n".join(f"- {a}" for a in artifacts)

    def _get_tool_defs(self) -> list[dict]:
        """Return the list of tool definitions available to the LLM.

        Delegates to ``self._tool_registry.get_definitions()`` if a
        ToolRegistry is configured; otherwise returns an empty list.
        """
        if self._tool_registry is not None:
            return self._tool_registry.get_definitions()
        return []

    def _execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """Execute a batch of tool calls and return result messages.

        Each result must have ``id`` and ``content`` keys so it can be
        appended as a ``role: "tool"`` message.

        Delegates to ``self._tool_registry.execute()`` with JSON argument
        parsing when a ToolRegistry is configured.
        """
        import json

        results: list[dict] = []
        for tc in tool_calls:
            if self._tool_registry is not None:
                try:
                    name = tc.get("name", "")
                    args_str = tc.get("arguments", "{}")
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    result = self._tool_registry.execute(name, args)
                    results.append({
                        "id": tc.get("id", ""),
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    })
                except Exception as exc:
                    results.append({
                        "id": tc.get("id", ""),
                        "content": f"Tool error: {exc}",
                    })
            else:
                results.append({
                    "id": tc.get("id", ""),
                    "content": f"Tool '{tc.get('name', 'unknown')}' not available",
                })
        return results

    @staticmethod
    def _format_tool_calls_for_message(tool_calls: list[dict]) -> list[dict]:
        """Convert LLMResponse tool_calls (flat) to the format expected in
        an assistant message (nested under ``function`` key).

        LLMResponse stores: ``{"id": ..., "type": ..., "name": ..., "arguments": ...}``
        Assistant message expects: ``{"id": ..., "type": ..., "function": {"name": ..., "arguments": ...}}``
        """
        formatted = []
        for tc in tool_calls:
            item = {
                "id": tc.get("id", ""),
                "type": tc.get("type", "function"),
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("arguments", ""),
                },
            }
            formatted.append(item)
        return formatted

    def _record_decision(self, phase, response: LLMResponse) -> None:
        """Record the phase completion decision.

        Stores phase result in *cognition_service* if available, otherwise
        no-op.
        """
        if self.cognition_service is not None:
            try:
                self.cognition_service.record_decision(
                    phase_id=phase.id,
                    phase_name=phase.name,
                    content=response.content,
                    tool_calls=response.tool_calls,
                    usage=response.usage,
                )
            except Exception:
                pass
