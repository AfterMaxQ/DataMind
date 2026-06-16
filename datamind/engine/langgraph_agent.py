"""LangGraph Agent Engine — SkillGraphBuilder, LangGraphAgent, and event types.

Replaces the v2 custom while-loop in DataMindAgent with a LangGraph
StateGraph-based execution engine.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.constants import END
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt

_log = logging.getLogger(__name__)

# ===========================================================================
# SkillState TypedDict
# ===========================================================================


class SkillState(TypedDict, total=False):
    """Graph state shared across all skill execution nodes.

    Attributes:
        session_id: Unique session identifier.
        skill_name: Name of the skill being executed.
        target: Target data file or resource.
        current_phase: Zero-based index into the phases list.
        phase_results: Mapping from phase id to result dict (content, status, etc.).
        messages: LLM conversation messages (system, user, assistant, tool).
        tool_calls: Accumulated tool calls across all phases.
        gate_decision: Last gate routing decision (``"approve"`` or ``"reject"``).
        result: Final workflow result (``"pass"``, ``"rejected"``, or ``None``).
    """

    session_id: str
    skill_name: str
    target: str
    current_phase: int
    phase_results: dict[str, Any]
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    gate_decision: str
    result: str | None


# ===========================================================================
# Event types
# ===========================================================================


class LangGraphEvent:
    """Base class for events returned by :meth:`LangGraphAgent.run`."""


@dataclass
class LangGraphPhaseComplete(LangGraphEvent):
    """An AUTO phase completed successfully.

    Attributes:
        phase_id: The id of the completed phase.
        state: Snapshot of the agent state after phase completion.
    """

    phase_id: str
    state: dict = field(default_factory=dict)


@dataclass
class LangGraphWaitForApproval(LangGraphEvent):
    """A GATE phase requires human approval.

    Attributes:
        phase_id: The id of the GATE phase awaiting approval.
        phase_name: Human-readable name of the GATE phase.
        interrupt_value: The value passed to ``interrupt()``.
    """

    phase_id: str
    phase_name: str
    interrupt_value: dict = field(default_factory=dict)


@dataclass
class LangGraphError(LangGraphEvent):
    """An error occurred during agent execution.

    Attributes:
        error_message: Description of the error.
    """

    error_message: str


@dataclass
class LangGraphComplete(LangGraphEvent):
    """All phases in the workflow have completed.

    Attributes:
        state: Final snapshot of the agent state.
    """

    state: dict = field(default_factory=dict)


# ===========================================================================
# SkillGraphBuilder
# ===========================================================================


class SkillGraphBuilder:
    """Constructs a :class:`StateGraph` from skill phase definitions.

    Detects skill complexity (routing or parallel phases) and builds either
    a linear or complex graph structure.

    Parameters:
        skill_def: Skill definition object with ``phases`` and optional
            ``frontmatter`` attributes.
        tool_registry: Optional :class:`~datamind.engine.tools.ToolRegistry` for tool execution.
        llm_client: Optional LLM client for real model calls (mockable for tests).
        prompt_manager: Optional prompt manager for template-based prompt assembly.
    """

    def __init__(self, skill_def, tool_registry=None, llm_client=None, prompt_manager=None):
        self.phases = list(skill_def.phases)
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.prompt_manager = prompt_manager
        self._frontmatter = getattr(skill_def, "frontmatter", {})

    # ------------------------------------------------------------------
    # Build entry point
    # ------------------------------------------------------------------

    def build(self, checkpointer=None):
        """Build and compile a graph, returning a runnable compiled graph.

        Parameters:
            checkpointer: Optional LangGraph checkpointer.  Defaults to
                :class:`~langgraph.checkpoint.memory.InMemorySaver` when
                ``None``.
        """
        if checkpointer is None:
            from langgraph.checkpoint.memory import InMemorySaver
            checkpointer = InMemorySaver()

        # Detect complexity — check for parallel or routing config
        has_parallel = any(
            getattr(p, "parallel", False) for p in self.phases
        )
        if has_parallel:
            builder = self._build_complex_graph()
        else:
            builder = self._build_linear_graph()
        return builder.compile(checkpointer=checkpointer)

    # ------------------------------------------------------------------
    # Linear graph
    # ------------------------------------------------------------------

    def _build_linear_graph(self) -> StateGraph:
        """Build a linear graph: one node per phase, sequential edges.

        After each GATE node, a conditional edge routes based on
        ``gate_decision``.  REJECT routing is read from
        ``self._frontmatter["routing"]["gate-{i}"]``; defaults to ``END``.
        """
        builder = StateGraph(SkillState)

        # Register nodes
        for i, phase in enumerate(self.phases):
            node_name = phase.id
            if phase.type == "AUTO":
                builder.add_node(node_name, self._make_auto_node(phase, i))
            else:
                builder.add_node(node_name, self._make_gate_node(phase, i))

        # Entry
        builder.add_edge(START, self.phases[0].id)

        self._add_edges(builder)
        return builder

    # ------------------------------------------------------------------
    # Complex graph (parallel / routing)
    # ------------------------------------------------------------------

    def _build_complex_graph(self) -> StateGraph:
        """Build a graph with parallel execution support.

        REJECT routing is read from ``self._frontmatter["routing"]["gate-{i}"]``;
        defaults to ``END``.
        """
        builder = StateGraph(SkillState)

        for i, phase in enumerate(self.phases):
            node_name = phase.id
            if getattr(phase, "parallel", False):
                builder.add_node(
                    node_name,
                    self._make_parallel_node(phase, i, getattr(phase, "parallel_config", {})),
                )
            elif phase.type == "AUTO":
                builder.add_node(node_name, self._make_auto_node(phase, i))
            else:
                builder.add_node(node_name, self._make_gate_node(phase, i))

        builder.add_edge(START, self.phases[0].id)

        self._add_edges(builder)
        return builder

    # ------------------------------------------------------------------
    # Edge building (shared by linear and complex graph builders)
    # ------------------------------------------------------------------

    def _add_edges(self, builder: StateGraph) -> None:
        """Add sequential and conditional edges for all phases.

        Reads REJECT routing from
        ``self._frontmatter["routing"]["gate-{i}"]``; defaults to ``END``.
        """
        routing = self._frontmatter.get("routing", {})

        # Inter-node edges
        for i in range(len(self.phases) - 1):
            current = self.phases[i]
            next_phase = self.phases[i + 1]
            if current.type == "GATE":
                routing_key = f"gate-{i + 1}"
                route_info = routing.get(routing_key, {})
                reject_target = route_info.get("reject", END)
                builder.add_conditional_edges(
                    current.id,
                    self._gate_router,
                    {"approve": next_phase.id, "reject": reject_target},
                )
            else:
                builder.add_edge(current.id, next_phase.id)

        # Final node → END
        last = self.phases[-1]
        if last.type == "GATE":
            builder.add_conditional_edges(
                last.id,
                self._gate_router,
                {"approve": END, "reject": END},
            )
        else:
            builder.add_edge(last.id, END)

    # ------------------------------------------------------------------
    # Node factories
    # ------------------------------------------------------------------

    def _make_auto_node(self, phase, index: int):
        """Return a node function for an AUTO phase.

        The node: assembles context, renders a prompt (via
        ``prompt_manager`` when available, or inline assembly as
        fallback), calls the LLM (with tool loop, max 5 turns), records
        the result, and advances ``current_phase``.

        When no ``llm_client`` is provided, the node records a mock result
        so that tests and skill structure validation can proceed without a
        live LLM.
        """

        def node(state: SkillState) -> dict:
            content = ""
            tool_calls: list[dict] = []
            phase_results = dict(state.get("phase_results", {}))
            messages: list[dict] = list(state.get("messages", []))

            if self.llm_client:
                # Assemble prompt — use prompt_manager if available
                if self.prompt_manager:
                    prompt_text = self.prompt_manager.render(
                        skill_name=state.get("skill_name", ""),
                        target=state.get("target", ""),
                        phase=phase,
                        phase_index=index,
                        total_phases=len(self.phases),
                    )
                else:
                    prompt_text = (
                        f"Skill: {state.get('skill_name', '')}\n"
                        f"Target: {state.get('target', '')}\n"
                        f"Phase: {phase.name} — {phase.description}\n"
                        f"Phase {index + 1}/{len(self.phases)}"
                    )
                system_msg = {"role": "system", "content": prompt_text}
                phase_messages = [system_msg]
                if messages:
                    phase_messages.extend(messages)

                # Tool definitions
                tool_defs = (
                    self.tool_registry.get_definitions()
                    if self.tool_registry
                    else []
                )

                # Initial LLM call
                response = self.llm_client.chat(
                    messages=phase_messages, tools=tool_defs
                )
                content = response.content or ""

                # Tool call loop (max 5 turns)
                if response.tool_calls:
                    tool_turns = 0
                    while response.tool_calls and tool_turns < 5:

                        # Execute tools via registry
                        if self.tool_registry:
                            for tc in response.tool_calls:
                                try:
                                    args = tc.get("arguments", {})
                                    if isinstance(args, str):
                                        try:
                                            args = json.loads(args)
                                        except json.JSONDecodeError:
                                            args = {}
                                    tc_result = self.tool_registry.execute(
                                        tc.get("name", ""), args
                                    )
                                except Exception as exc:
                                    tc_result = {"error": str(exc)}
                                tool_calls.append({
                                    "id": tc.get("id", ""),
                                    "name": tc.get("name", ""),
                                    "result": tc_result,
                                })

                        # Build assistant + tool messages for next turn
                        assistant_msg = {
                            "role": "assistant",
                            "content": response.content or "",
                        }
                        assistant_msg["tool_calls"] = self._format_tool_calls(
                            response.tool_calls
                        )
                        phase_messages.append(assistant_msg)

                        for tc in response.tool_calls:
                            # Look up the actual execution result from
                            # accumulated tool_calls (not the raw call
                            # dict, which has no "result" key).
                            matched = next(
                                (t for t in tool_calls if t.get("id") == tc.get("id")),
                                None,
                            )
                            tc_result = matched.get("result", {}) if matched else {}
                            phase_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": json.dumps(
                                    tc_result, ensure_ascii=False
                                ),
                            })

                        response = self.llm_client.chat(
                            messages=phase_messages, tools=tool_defs
                        )
                        tool_turns += 1

                    content = response.content or ""

                # Append phase messages to global messages
                messages.extend(phase_messages)
            else:
                # No LLM client — produce a deterministic mock result
                content = f"[{phase.name}] completed (mock — no LLM client)"

            # Record phase result
            phase_results[phase.id] = {
                "content": content,
                "status": "complete",
                "tool_calls": tool_calls,
            }

            # Advance to next phase or mark complete
            updates: dict = {
                "phase_results": phase_results,
                "messages": messages,
                "gate_decision": "",
            }

            if index + 1 >= len(self.phases):
                updates["result"] = "pass"
            else:
                updates["current_phase"] = index + 1

            return updates

        return node

    def _make_gate_node(self, phase, index: int):
        """Return a node function for a GATE phase.

        Calls ``interrupt()`` to pause execution and wait for human input.
        On resume, checks the decision and sets ``gate_decision`` accordingly.
        """

        def node(state: SkillState) -> dict:
            gate_value = interrupt({
                "phase_id": phase.id,
                "phase_name": phase.name,
                "description": phase.description,
                "message": f"Approve phase: {phase.name}?",
            })

            approved = False
            if isinstance(gate_value, dict):
                approved = gate_value.get("approved", False)
            elif isinstance(gate_value, bool):
                approved = gate_value
            elif isinstance(gate_value, str):
                approved = gate_value.lower() in ("yes", "true", "approve", "1")

            phase_results = dict(state.get("phase_results", {}))

            if approved:
                phase_results[phase.id] = {
                    "decision": gate_value if isinstance(gate_value, dict) else {"approved": True},
                    "status": "approved",
                }
                updates: dict = {
                    "gate_decision": "approve",
                    "phase_results": phase_results,
                }
                if index + 1 >= len(self.phases):
                    updates["result"] = "pass"
                else:
                    updates["current_phase"] = index + 1
            else:
                phase_results[phase.id] = {
                    "decision": gate_value if isinstance(gate_value, dict) else {"approved": False},
                    "status": "rejected",
                }
                updates = {
                    "gate_decision": "reject",
                    "phase_results": phase_results,
                    "result": "rejected",
                }

            return updates

        return node

    def _make_parallel_node(self, phase, index: int, config: dict):
        """Return a node function for fan-out parallel execution.

        Used when a phase is marked with ``parallel=True`` in its definition.
        """

        def node(state: SkillState) -> dict:
            # For now, fall through like an AUTO node; parallel semantics
            # are implemented via LangGraph Send API in a future iteration.
            fn = self._make_auto_node(phase, index)
            return fn(state)

        return node

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    @staticmethod
    def _gate_router(state: SkillState) -> str:
        """Conditional router: reads ``gate_decision`` and returns routing key.

        Returns:
            ``"approve"`` or ``"reject"``.
        """
        decision = state.get("gate_decision", "")
        if decision == "approve":
            return "approve"
        return "reject"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tool_calls(tool_calls: list[dict]) -> list[dict]:
        """Convert flat tool calls to the nested ``function`` message format."""
        formatted = []
        for tc in tool_calls:
            formatted.append({
                "id": tc.get("id", ""),
                "type": tc.get("type", "function"),
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(
                        tc.get("arguments", "{}"), ensure_ascii=False
                    )
                    if isinstance(tc.get("arguments"), dict)
                    else str(tc.get("arguments", "{}")),
                },
            })
        return formatted


# ===========================================================================
# LangGraphAgent
# ===========================================================================


class LangGraphAgent:
    """LangGraph-based execution engine for skill workflows.

    Uses a pre-compiled graph from :class:`SkillGraphBuilder.build` and
    drives execution across skill phases with checkpoint-based resume.

    Parameters:
        graph_builder: A configured :class:`SkillGraphBuilder` whose
            ``build()`` returns a compiled graph.
        skill_yaml_path: Optional path to a ``.skill.yaml`` file for
            persisting state on phase transitions.
    """

    def __init__(self, graph_builder: SkillGraphBuilder, skill_yaml_path=None):
        self.graph_builder = graph_builder
        self.graph = graph_builder.build()
        self.config: dict = {"configurable": {"thread_id": "default"}}
        self.skill_yaml_path = skill_yaml_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, initial_state: SkillState, thread_id: str | None = None) -> LangGraphEvent:
        """Invoke the graph until interrupt or completion.

        Args:
            initial_state: The starting :class:`SkillState`.
            thread_id: Optional LangGraph thread id for checkpoint isolation.

        Returns:
            A :class:`LangGraphEvent` subclass:
            - :class:`LangGraphComplete` — workflow finished.
            - :class:`LangGraphWaitForApproval` — paused at a GATE phase.
            - :class:`LangGraphError` — an error occurred.
        """
        if thread_id:
            self.config["configurable"]["thread_id"] = thread_id

        try:
            final_state = self.graph.invoke(initial_state, self.config)
            return self._handle_result(final_state)
        except Exception as exc:
            return LangGraphError(error_message=str(exc))

    def resume(self, decision) -> LangGraphEvent:
        """Resume graph execution after a GATE interrupt.

        Args:
            decision: The value passed to :func:`interrupt` on resume.
                Typically ``{"approved": True}`` or ``{"approved": False}``.

        Returns:
            A :class:`LangGraphEvent` subclass.
        """
        try:
            final_state = self.graph.invoke(
                Command(resume=decision), self.config
            )
            return self._handle_result(final_state)
        except Exception as exc:
            return LangGraphError(error_message=str(exc))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_result(self, state: SkillState) -> LangGraphEvent:
        """Interpret the final graph state and return an appropriate event.

        In LangGraph 1.2.5, ``interrupt()`` stores pending interrupts in
        ``state['__interrupt__']`` instead of raising ``GraphInterrupt``.
        We check for pending interrupts first.

        ``_update_skill_yaml`` is called on **every** transition so the
        ``.skill.yaml`` stays current even during GATE pauses.
        """
        # Persist on every transition (D4)
        self._update_skill_yaml(state)

        # Check for pending interrupts (GATE phases paused)
        pending_interrupts = state.get("__interrupt__", [])
        if pending_interrupts and not state.get("result"):
            interrupt_obj = pending_interrupts[0]
            interrupt_value = getattr(interrupt_obj, "value", {})
            phase_id = ""
            phase_name = ""
            if isinstance(interrupt_value, dict):
                phase_id = interrupt_value.get("phase_id", "")
                phase_name = interrupt_value.get("phase_name", "")
            return LangGraphWaitForApproval(
                phase_id=phase_id,
                phase_name=phase_name,
                interrupt_value=interrupt_value,
            )

        result = state.get("result")
        if result in ("pass", "rejected"):
            return LangGraphComplete(state=dict(state))

        # Intermediate completion (shouldn't normally happen)
        phase_id = ""
        if self.graph_builder.phases:
            phase_idx = state.get("current_phase", 0)
            if 0 <= phase_idx < len(self.graph_builder.phases):
                phase_id = self.graph_builder.phases[phase_idx].id
        return LangGraphPhaseComplete(phase_id=phase_id, state=dict(state))

    def _update_skill_yaml(self, state: SkillState) -> None:
        """Persist the current state to ``.skill.yaml`` if a path is configured."""
        if not self.skill_yaml_path:
            return
        try:
            data = {
                "skill_name": state.get("skill_name", ""),
                "target": state.get("target", ""),
                "session_id": state.get("session_id", ""),
                "current_phase": state.get("current_phase", 0),
                "phase_results": state.get("phase_results", {}),
                "gate_decision": state.get("gate_decision", ""),
                "result": state.get("result"),
            }
            yaml_path = Path(self.skill_yaml_path)
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
        except Exception:
            _log.warning("Failed to update .skill.yaml", exc_info=True)

