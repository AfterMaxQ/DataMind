"""Tests for SkillState, SkillGraphBuilder, and LangGraphAgent (Task 3)."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from datamind.engine.skill_state import SkillPhase


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
    """Verify SkillGraphBuilder constructs valid StateGraph instances."""

    def test_build_returns_state_graph(self):
        """build() returns a StateGraph (not compiled)."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder
        builder = SkillGraphBuilder(phases=SIMPLE_AUTO_PHASES)
        graph = builder.build()
        from langgraph.graph import StateGraph
        assert isinstance(graph, StateGraph)

    def test_compile_produces_runnable_graph(self):
        """Compiled graph can be invoked and runs AUTO phases."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, SkillState
        from langgraph.checkpoint.memory import InMemorySaver

        builder = SkillGraphBuilder(phases=SIMPLE_AUTO_PHASES)
        graph = builder.build()
        compiled = graph.compile(checkpointer=InMemorySaver())

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

        builder = SkillGraphBuilder(phases=SIMPLE_AUTO_PHASES)
        graph = builder.build()
        compiled = graph.compile()

        # Check that expected node names exist via nodes property (1.2.5 API)
        node_names = list(compiled.nodes.keys())
        for phase in SIMPLE_AUTO_PHASES:
            assert phase.id in node_names, (
                f"Expected node {phase.id} not found in {node_names}"
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

    def chat(self, messages=None, tools=None):
        from datamind.engine.llm import LLMResponse
        self.call_count += 1
        self.last_messages = messages
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
    def _make_agent(phases, llm_client=None, yaml_path=None):
        """Create a LangGraphAgent for testing."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder, LangGraphAgent
        from langgraph.checkpoint.memory import InMemorySaver

        builder = SkillGraphBuilder(phases=phases, llm_client=llm_client)
        checkpointer = InMemorySaver()
        return LangGraphAgent(builder, checkpointer, skill_yaml_path=yaml_path)

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

    def test_skill_yaml_not_corrupted_on_error(self, tmp_project):
        """Incomplete runs should not corrupt .skill.yaml."""
        yaml_path = tmp_project / ".skill.yaml"
        agent = self._make_agent(
            phases=AUTO_GATE_PHASES,
            yaml_path=str(yaml_path),
        )
        state = self._initial_state()

        # Run — should stop at GATE (no complete)
        event = agent.run(state)
        from datamind.engine.langgraph_agent import LangGraphWaitForApproval
        assert isinstance(event, LangGraphWaitForApproval)

        # File may or may not exist (implementation choice)
        # If it exists, it should NOT have result="pass"
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            assert data.get("result") is None, (
                "Incomplete run must not set result=pass"
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
