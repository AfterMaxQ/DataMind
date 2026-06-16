"""Tests for SkillState, SkillGraphBuilder, and LangGraphAgent (Task 3)."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml
from langgraph.graph import StateGraph

from datamind.engine.skill_state import SkillPhase


# ===========================================================================
# Mock objects
# ===========================================================================

class MockSkillDef:
    """Mock skill definition for testing SkillGraphBuilder constructor."""

    def __init__(self, phases, frontmatter=None):
        self.phases = list(phases)
        self.frontmatter = frontmatter or {}


class MockPromptManager:
    """Mock prompt manager for testing prompt_manager integration."""

    def __init__(self):
        self.render_calls = []

    def render(self, skill_name="", phase=None, phase_index=0, total_phases=0,
               target="", **kwargs):
        self.render_calls.append({
            "skill_name": skill_name,
            "phase": phase,
            "phase_index": phase_index,
            "total_phases": total_phases,
            "target": target,
        })
        return f"Rendered prompt for {skill_name}"


# ===========================================================================
# 1. SkillState TypedDict
# ===========================================================================


class TestSkillState:
    """Verify SkillState TypedDict has all required fields."""

    def test_skill_state_required_fields(self):
        """All 9 fields must be present."""
        from datamind.engine.langgraph_agent import SkillState

        # Build a minimal valid state dict
        state: SkillState = {
            "session_id": "test-session",
            "skill_name": "data-cleaning",
            "target": "sales.csv",
            "current_phase": 0,
            "phase_results": {},
            "messages": [],
            "tool_calls": [],
            "gate_decision": "",
            "result": None,
        }

        expected = {
            "session_id", "skill_name", "target", "current_phase",
            "phase_results", "messages", "tool_calls", "gate_decision", "result",
        }
        assert set(state.keys()) == expected

    def test_skill_state_defaults(self):
        """Verify optional fields have sensible defaults when creating from partial."""
        from datamind.engine.langgraph_agent import SkillState

        state: SkillState = {
            "session_id": "s1",
            "skill_name": "test",
            "target": "f.csv",
        }
        # remaining fields should be fillable
        state["current_phase"] = 0
        state["phase_results"] = {}
        state["gate_decision"] = ""
        assert state["session_id"] == "s1"
        assert state["current_phase"] == 0


# ===========================================================================
# 2. SkillGraphBuilder
# ===========================================================================


SIMPLE_AUTO_PHASES = [
    SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze data"),
    SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute plan"),
]

AUTO_GATE_PHASES = [
    SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze data"),
    SkillPhase(id="gate-approve", name="Gate: Approve", type="GATE", description="Human approval"),
    SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute plan"),
]


class TestSkillGraphBuilder:
    """Verify SkillGraphBuilder constructs valid compiled graphs."""

    # ------------------------------------------------------------------
    # D1: Constructor accepts skill_def, prompt_manager
    # ------------------------------------------------------------------

    def test_constructor_accepts_skill_def(self):
        """D1: Constructor accepts skill_def, extracts phases and frontmatter."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        frontmatter = {"routing": {"gate-0": {"reject": "analyze"}}}
        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES, frontmatter=frontmatter)
        builder = SkillGraphBuilder(skill_def=skill_def)
        assert len(builder.phases) == 2
        assert builder.phases[0].id == "analyze"
        assert builder._frontmatter == frontmatter

    def test_prompt_manager_used_when_provided(self):
        """D1: prompt_manager.render() is used instead of inline prompt assembly."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, SkillState

        prompt_mgr = MockPromptManager()
        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES)
        # Must provide an llm_client so the auto node enters the prompt path
        llm = MockLLMClient()
        builder = SkillGraphBuilder(
            skill_def=skill_def, llm_client=llm, prompt_manager=prompt_mgr
        )
        compiled = builder.build()

        initial: SkillState = {
            "session_id": "s1",
            "skill_name": "test-skill",
            "target": "test.csv",
            "current_phase": 0,
            "phase_results": {},
            "messages": [],
            "tool_calls": [],
            "gate_decision": "",
            "result": None,
        }

        compiled.invoke(initial, {"configurable": {"thread_id": "t2"}})
        assert len(prompt_mgr.render_calls) == 2, (
            f"Expected 2 render calls (one per AUTO phase), got {len(prompt_mgr.render_calls)}"
        )

    def test_prompt_manager_none_falls_back_to_inline(self):
        """D1: When prompt_manager is None, falls back to inline prompt (existing behavior)."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, SkillState

        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES)
        builder = SkillGraphBuilder(skill_def=skill_def, prompt_manager=None)
        compiled = builder.build()

        initial: SkillState = {
            "session_id": "s1",
            "skill_name": "test-skill",
            "target": "test.csv",
            "current_phase": 0,
            "phase_results": {},
            "messages": [],
            "tool_calls": [],
            "gate_decision": "",
            "result": None,
        }

        result = compiled.invoke(initial, {"configurable": {"thread_id": "t3"}})
        assert result["result"] == "pass"

    # ------------------------------------------------------------------
    # D2: build() returns compiled graph
    # ------------------------------------------------------------------

    def test_build_returns_compiled_graph(self):
        """D2: build() returns a compiled graph (not an uncompiled StateGraph)."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES)
        builder = SkillGraphBuilder(skill_def=skill_def)
        graph = builder.build()

        # Must NOT be a raw StateGraph (must be compiled)
        assert not isinstance(graph, StateGraph), (
            "build() must return compiled graph, not raw StateGraph"
        )
        # Must have invoke() for execution
        assert hasattr(graph, "invoke"), "Compiled graph must have invoke()"

    def test_compiled_graph_runs_phases(self):
        """D2: Compiled graph from build() can be invoked directly without manual compile."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, SkillState

        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES)
        builder = SkillGraphBuilder(skill_def=skill_def)
        compiled = builder.build()

        initial: SkillState = {
            "session_id": "s1",
            "skill_name": "test-skill",
            "target": "test.csv",
            "current_phase": 0,
            "phase_results": {},
            "messages": [],
            "tool_calls": [],
            "gate_decision": "",
            "result": None,
        }

        result = compiled.invoke(initial, {"configurable": {"thread_id": "t1"}})
        assert result["result"] == "pass"
        assert "analyze" in result["phase_results"]
        assert "execute" in result["phase_results"]
        assert result["phase_results"]["analyze"]["status"] == "complete"

    def test_linear_graph_has_correct_nodes(self):
        """Linear graph has one node per phase."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        skill_def = MockSkillDef(phases=SIMPLE_AUTO_PHASES)
        builder = SkillGraphBuilder(skill_def=skill_def)
        compiled = builder.build()

        node_names = list(compiled.nodes.keys())
        for phase in SIMPLE_AUTO_PHASES:
            assert phase.id in node_names, (
                f"Expected node {phase.id} not found in {node_names}"
            )

    # ------------------------------------------------------------------
    # D3: REJECT routes to fallback phase
    # ------------------------------------------------------------------

    def test_reject_routes_to_fallback_from_frontmatter(self):
        """D3: REJECT edge routes to frontmatter-configured fallback phase."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        frontmatter = {
            "routing": {
                "gate-2": {"reject": "analyze"}
            }
        }
        skill_def = MockSkillDef(phases=AUTO_GATE_PHASES, frontmatter=frontmatter)
        builder = SkillGraphBuilder(skill_def=skill_def)
        compiled = builder.build()

        # Inspect the gate node's conditional branch
        branches = compiled.builder.branches
        gate_branch = branches.get("gate-approve")
        assert gate_branch is not None, "Gate node must have a conditional branch"
        # The branch dict is keyed by router function name
        branch_spec = list(gate_branch.values())[0]
        assert branch_spec.ends["reject"] == "analyze", (
            f"Reject should route to 'analyze', got {branch_spec.ends.get('reject')}"
        )

    def test_reject_defaults_to_end_without_routing(self):
        """D3: REJECT edge defaults to END when no routing config is present."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        skill_def = MockSkillDef(phases=AUTO_GATE_PHASES)
        builder = SkillGraphBuilder(skill_def=skill_def)
        compiled = builder.build()

        branches = compiled.builder.branches
        gate_branch = branches.get("gate-approve")
        assert gate_branch is not None
        # The branch dict is keyed by router function name
        branch_spec = list(gate_branch.values())[0]
        # LangGraph represents END as "__end__"
        assert branch_spec.ends["reject"] == "__end__", (
            f"Reject should default to __end__, got {branch_spec.ends.get('reject')}"
        )


# ===========================================================================
# 3. LangGraphAgent
# ===========================================================================


class MockLLMClient:
    """Minimal mock LLM client for testing without real API calls."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.last_messages = None
        self.all_messages: list = []  # N1: capture all call messages for inspection

    def chat(self, messages=None, tools=None):
        from datamind.engine.llm import LLMResponse
        self.call_count += 1
        self.last_messages = messages
        self.all_messages.append(messages or [])  # N1: capture every call
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return LLMResponse(
            content="mock response",
            tool_calls=[],
            usage={"prompt_tokens": 5, "completion_tokens": 3},
        )


class TestLangGraphAgent:
    """Verify LangGraphAgent run/resume/event lifecycle."""

    # ------------------------------------------------------------------
    # Fixture helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_agent(phases, llm_client=None, yaml_path=None, frontmatter=None):
        """Create a LangGraphAgent for testing."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, LangGraphAgent

        skill_def = MockSkillDef(phases=phases, frontmatter=frontmatter)
        builder = SkillGraphBuilder(skill_def=skill_def, llm_client=llm_client)
        return LangGraphAgent(builder, skill_yaml_path=yaml_path)

    @staticmethod
    def _initial_state(skill_name="test-skill", target="test.csv"):
        """Create a minimal initial SkillState."""
        return {
            "session_id": "s1",
            "skill_name": skill_name,
            "target": target,
            "current_phase": 0,
            "phase_results": {},
            "messages": [],
            "tool_calls": [],
            "gate_decision": "",
            "result": None,
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_run_linear_skill_completes(self):
        """run() completes a skill with only AUTO phases (no LLM needed)."""
        agent = self._make_agent(phases=SIMPLE_AUTO_PHASES)
        state = self._initial_state()
        event = agent.run(state)

        from datamind.engine.langgraph_agent import LangGraphComplete
        assert isinstance(event, LangGraphComplete)
        assert event.state["result"] == "pass"
        assert "analyze" in event.state["phase_results"]
        assert "execute" in event.state["phase_results"]

    def test_run_with_llm_calls_llm(self):
        """run() calls the LLM for each AUTO phase when llm_client is provided."""
        llm = MockLLMClient()
        agent = self._make_agent(phases=SIMPLE_AUTO_PHASES, llm_client=llm)
        state = self._initial_state()
        event = agent.run(state)

        from datamind.engine.langgraph_agent import LangGraphComplete
        assert isinstance(event, LangGraphComplete)
        assert llm.call_count == 2  # one per AUTO phase

    def test_run_with_gate_interrupts(self, tmp_project):
        """run() with a GATE phase interrupts and returns WaitForApproval."""
        agent = self._make_agent(phases=AUTO_GATE_PHASES)
        state = self._initial_state()
        event = agent.run(state)

        from datamind.engine.langgraph_agent import LangGraphWaitForApproval
        assert isinstance(event, LangGraphWaitForApproval)
        assert event.phase_id == "gate-approve"
        assert event.phase_name == "Gate: Approve"

    def test_resume_approve_continues(self):
        """resume() with approved decision continues execution."""
        agent = self._make_agent(phases=AUTO_GATE_PHASES)
        state = self._initial_state()

        # First run — should stop at GATE
        event1 = agent.run(state)
        from datamind.engine.langgraph_agent import LangGraphWaitForApproval
        assert isinstance(event1, LangGraphWaitForApproval)

        # Resume with approval
        event2 = agent.resume({"approved": True})
        from datamind.engine.langgraph_agent import LangGraphComplete
        assert isinstance(event2, LangGraphComplete)
        assert event2.state["result"] == "pass"
        assert "execute" in event2.state["phase_results"]

    def test_resume_reject_ends(self):
        """resume() with rejected decision ends the workflow."""
        agent = self._make_agent(phases=AUTO_GATE_PHASES)
        state = self._initial_state()

        # First run — stops at GATE
        event1 = agent.run(state)
        from datamind.engine.langgraph_agent import LangGraphWaitForApproval
        assert isinstance(event1, LangGraphWaitForApproval)

        # Resume with rejection
        event2 = agent.resume({"approved": False})
        from datamind.engine.langgraph_agent import LangGraphComplete
        assert isinstance(event2, LangGraphComplete)
        assert event2.state["result"] == "rejected"

    def test_skill_yaml_updated_on_complete(self, tmp_project):
        """.skill.yaml is written when a skill completes."""
        yaml_path = tmp_project / ".skill.yaml"
        agent = self._make_agent(
            phases=SIMPLE_AUTO_PHASES,
            yaml_path=str(yaml_path),
        )
        state = self._initial_state()
        agent.run(state)

        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["skill_name"] == "test-skill"
        assert data["target"] == "test.csv"
        assert data["result"] == "pass"
        assert "analyze" in data["phase_results"]

    def test_skill_yaml_written_on_gate_interrupt(self, tmp_project):
        """D4: .skill.yaml is written on EVERY state transition, including gate interrupt."""
        yaml_path = tmp_project / ".skill.yaml"
        agent = self._make_agent(
            phases=AUTO_GATE_PHASES,
            yaml_path=str(yaml_path),
        )
        state = self._initial_state()

        # Run — should stop at GATE (interrupt, not complete)
        event = agent.run(state)
        from datamind.engine.langgraph_agent import LangGraphWaitForApproval
        assert isinstance(event, LangGraphWaitForApproval)

        # D4: File MUST exist after interrupt (every transition)
        assert yaml_path.exists(), (
            ".skill.yaml must be written on every state transition (D4)"
        )
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["skill_name"] == "test-skill"
        # Result should be None (not yet complete)
        assert data.get("result") is None, (
            "Interrupted run must not set result=pass"
        )

    def test_run_with_thread_id_configures_thread(self):
        """run() with explicit thread_id uses that thread."""
        agent = self._make_agent(phases=SIMPLE_AUTO_PHASES)
        state = self._initial_state()
        event = agent.run(state, thread_id="custom-thread-42")

        from datamind.engine.langgraph_agent import LangGraphComplete
        assert isinstance(event, LangGraphComplete)
        # Thread ID should be set in the agent config
        assert agent.config["configurable"]["thread_id"] == "custom-thread-42"

    def test_event_types_hierarchy(self):
        """Verify all event types are proper dataclasses/classes."""
        from datamind.engine.langgraph_agent import (
            LangGraphEvent,
            LangGraphPhaseComplete,
            LangGraphWaitForApproval,
            LangGraphError,
            LangGraphComplete,
        )

        # Base is a class (not dataclass)
        assert isinstance(LangGraphEvent(), LangGraphEvent)

        # Phase complete
        pc = LangGraphPhaseComplete(phase_id="analyze", state={"result": None})
        assert pc.phase_id == "analyze"
        assert isinstance(pc, LangGraphEvent)

        # Wait for approval
        wfa = LangGraphWaitForApproval(
            phase_id="gate-1",
            phase_name="Gate",
            interrupt_value={"msg": "approve?"},
        )
        assert wfa.phase_id == "gate-1"
        assert isinstance(wfa, LangGraphEvent)

        # Error
        err = LangGraphError(error_message="something went wrong")
        assert err.error_message == "something went wrong"
        assert isinstance(err, LangGraphEvent)

        # Complete
        comp = LangGraphComplete(
            state={"result": "pass", "phase_results": {"a": {}}},
        )
        assert comp.state["result"] == "pass"
        assert isinstance(comp, LangGraphEvent)

    # ------------------------------------------------------------------
    # C1: Tool call accumulation produces malformed list
    # ------------------------------------------------------------------

    def test_tool_calls_clean_no_raw_objects(self):
        """C1: tool_calls list contains only result dicts, no raw call objects."""
        from datamind.engine.llm import LLMResponse
        from datamind.engine.langgraph_agent import (
            LangGraphAgent, LangGraphComplete, SkillGraphBuilder,
        )
        from datamind.engine.tools import ToolRegistry

        # LLM returns 1 tool call, then empty (ends the while loop)
        tool_call = {
            "id": "tc-001",
            "type": "function",
            "name": "echo",
            "arguments": '{"msg": "hello"}',
        }
        llm = MockLLMClient(responses=[
            LLMResponse(content="Calling tool", tool_calls=[tool_call]),
            LLMResponse(content="Done", tool_calls=[]),
        ])

        reg = ToolRegistry()
        reg.register(
            "echo",
            {"type": "function", "function": {
                "name": "echo",
                "description": "Echo tool",
                "parameters": {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                },
            }},
            lambda msg="": {"echo": msg},
        )

        single_auto = [SkillPhase(id="step1", name="Step1", type="AUTO", description="Step 1")]
        skill_def = MockSkillDef(phases=single_auto)
        builder = SkillGraphBuilder(
            skill_def=skill_def, llm_client=llm, tool_registry=reg,
        )
        agent = LangGraphAgent(builder)

        state = self._initial_state()
        event = agent.run(state)

        assert isinstance(event, LangGraphComplete)
        phase_result = event.state["phase_results"]["step1"]
        tool_calls = phase_result["tool_calls"]

        # Must have exactly 1 entry (processed result only, no raw call object)
        assert len(tool_calls) == 1, (
            f"Expected 1 tool call entry, got {len(tool_calls)}: {tool_calls}"
        )
        # Verify it is a result dict (has "result"), NOT a raw call dict (has "arguments")
        assert "result" in tool_calls[0], (
            f"Expected 'result' key in tool call entry, got keys: {list(tool_calls[0].keys())}"
        )
        assert "arguments" not in tool_calls[0], (
            "Raw call object with 'arguments' key must not appear in tool_calls list"
        )
        assert tool_calls[0]["id"] == "tc-001"
        assert tool_calls[0]["name"] == "echo"

    # ------------------------------------------------------------------
    # I2: Tool-call execution path test
    # ------------------------------------------------------------------

    def test_tool_call_execution_loop(self):
        """I2: Tool call execution path — loop runs and results are recorded."""
        from datamind.engine.llm import LLMResponse
        from datamind.engine.langgraph_agent import (
            LangGraphAgent, LangGraphComplete, SkillGraphBuilder,
        )
        from datamind.engine.tools import ToolRegistry

        # LLM returns 2 tool calls, then finishes
        tool_call1 = {
            "id": "tc-1",
            "type": "function",
            "name": "echo",
            "arguments": '{"msg": "hello"}',
        }
        tool_call2 = {
            "id": "tc-2",
            "type": "function",
            "name": "double",
            "arguments": '{"n": 21}',
        }
        llm = MockLLMClient(responses=[
            LLMResponse(content="Calling tools", tool_calls=[tool_call1, tool_call2]),
            LLMResponse(content="All done", tool_calls=[]),
        ])

        reg = ToolRegistry()
        reg.register(
            "echo",
            {"type": "function", "function": {
                "name": "echo", "description": "Echo",
                "parameters": {"type": "object", "properties": {"msg": {"type": "string"}}},
            }},
            lambda msg="": {"echo": msg},
        )
        reg.register(
            "double",
            {"type": "function", "function": {
                "name": "double", "description": "Double a number",
                "parameters": {"type": "object", "properties": {"n": {"type": "number"}}},
            }},
            lambda n=0: {"double": n * 2},
        )

        single_auto = [SkillPhase(id="step1", name="Step1", type="AUTO", description="Step 1")]
        skill_def = MockSkillDef(phases=single_auto)
        builder = SkillGraphBuilder(
            skill_def=skill_def, llm_client=llm, tool_registry=reg,
        )
        agent = LangGraphAgent(builder)

        state = self._initial_state()
        event = agent.run(state)

        assert isinstance(event, LangGraphComplete)

        # Tool results recorded in phase_results
        phase_result = event.state["phase_results"]["step1"]
        tool_calls = phase_result["tool_calls"]
        assert len(tool_calls) == 2, (
            f"Expected 2 tool call results, got {len(tool_calls)}: {tool_calls}"
        )
        assert tool_calls[0]["name"] == "echo"
        assert tool_calls[0]["result"] == {"echo": "hello"}
        assert tool_calls[1]["name"] == "double"
        assert tool_calls[1]["result"] == {"double": 42}

        # LLM called exactly 2 times (initial + one follow-up after tool results)
        assert llm.call_count == 2, (
            f"Expected 2 LLM calls (initial + follow-up), got {llm.call_count}"
        )

    # ------------------------------------------------------------------
    # N1: Tool result messages reach the LLM with actual results
    # ------------------------------------------------------------------

    def test_tool_result_messages_contain_actual_results(self):
        """N1: Tool result messages in follow-up LLM calls contain actual execution
        output, not empty ``{}``.

        The existing tool execution loop stores results in the ``tool_calls`` list
        but the message-building loop reads ``tc.get("result", {})`` from raw call
        dicts (which never have a ``result`` key). This test verifies that the
        follow-up LLM call receives tool messages with real content.
        """
        from datamind.engine.llm import LLMResponse
        from datamind.engine.langgraph_agent import (
            LangGraphAgent, LangGraphComplete, SkillGraphBuilder,
        )
        from datamind.engine.tools import ToolRegistry

        # LLM returns 2 tool calls, then finishes
        tool_call1 = {
            "id": "tc-1",
            "type": "function",
            "name": "echo",
            "arguments": '{"msg": "hello"}',
        }
        tool_call2 = {
            "id": "tc-2",
            "type": "function",
            "name": "double",
            "arguments": '{"n": 21}',
        }
        llm = MockLLMClient(responses=[
            LLMResponse(content="Calling tools", tool_calls=[tool_call1, tool_call2]),
            LLMResponse(content="All done", tool_calls=[]),
        ])

        reg = ToolRegistry()
        reg.register(
            "echo",
            {"type": "function", "function": {
                "name": "echo", "description": "Echo",
                "parameters": {"type": "object", "properties": {"msg": {"type": "string"}}},
            }},
            lambda msg="": {"echo": msg},
        )
        reg.register(
            "double",
            {"type": "function", "function": {
                "name": "double", "description": "Double a number",
                "parameters": {"type": "object", "properties": {"n": {"type": "number"}}},
            }},
            lambda n=0: {"double": n * 2},
        )

        single_auto = [SkillPhase(id="step1", name="Step1", type="AUTO", description="Step 1")]
        skill_def = MockSkillDef(phases=single_auto)
        builder = SkillGraphBuilder(
            skill_def=skill_def, llm_client=llm, tool_registry=reg,
        )
        agent = LangGraphAgent(builder)

        state = self._initial_state()
        event = agent.run(state)

        assert isinstance(event, LangGraphComplete)

        # The follow-up LLM call (call 2) must contain tool result messages
        assert len(llm.all_messages) >= 2, (
            f"Expected at least 2 LLM calls, got {len(llm.all_messages)}"
        )
        follow_up_messages = llm.all_messages[1]  # second call

        # Find tool messages in the follow-up call
        tool_msgs = [m for m in follow_up_messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 2, (
            f"Expected 2 tool messages in follow-up call, got {len(tool_msgs)}: {tool_msgs}"
        )

        # Parse the content of each tool message
        for msg in tool_msgs:
            content = msg.get("content", "")
            parsed = __import__("json").loads(content)
            assert parsed != {}, (
                f"Tool message content must NOT be empty dict, got: {content}"
            )
            assert "tool_call_id" in msg, (
                f"Tool message must have tool_call_id: {msg}"
            )
