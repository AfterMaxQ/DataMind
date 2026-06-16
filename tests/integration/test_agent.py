"""Integration tests for DataMindAgent loop, GATE pause/resume, and tool dispatch."""

from datamind.engine.llm import LLMResponse
from datamind.engine.skill_state import (
    SkillPhase,
    SkillSessionState,
    SkillStateMachine,
    PhaseStatus,
)

# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Returns pre-configured LLMResponse objects in sequence.

    After exhausting *responses*, returns a default simple text response.
    """

    def __init__(self, responses=None, model="mock-model"):
        self.responses = list(responses) if responses else []
        self.model = model
        self.call_count = 0
        self.calls = []

    def chat(self, messages, tools=None, stream=False, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools})
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return LLMResponse(
            content="Default mock response",
            model=self.model,
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

    def list_models(self):
        return [self.model]


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

AUTO_GATE_AUTO_PHASES = [
    SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze data"),
    SkillPhase(id="gate-review", name="Gate: Review", type="GATE", description="Human review"),
    SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute plan"),
]

FULL_WORKFLOW_PHASES = [
    SkillPhase(id="understand", name="Understand", type="AUTO", description="Understand request"),
    SkillPhase(id="gate-plan", name="Gate: Plan", type="GATE", description="Approve plan"),
    SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute plan"),
    SkillPhase(id="gate-result", name="Gate: Result", type="GATE", description="Sign off"),
    SkillPhase(id="deliver", name="Deliver", type="AUTO", description="Deliver results"),
]


def _make_state(phases, first_phase_index=0):
    """Build a SkillSessionState with the given phases active."""
    p = phases
    first = p[first_phase_index]
    phases_dict = {ph.id: PhaseStatus.PENDING.value for ph in p}
    phases_dict[first.id] = PhaseStatus.IN_PROGRESS.value

    return SkillSessionState(
        skill="test-skill",
        target="test-data.csv",
        session="2026-06-15T143000Z-test",
        started_at="2026-06-15T14:30:00Z",
        completed_at=None,
        phase=first.id,
        phases=phases_dict,
        artifacts={},
        result=None,
        usage={},
    )


def _make_sm(phases, first_phase_index=0):
    """Build a SkillStateMachine with test phase definitions."""
    return SkillStateMachine(_make_state(phases, first_phase_index), phases)


def _make_prompt_manager():
    """Return a minimal prompt manager for testing."""
    from datamind.engine.prompt import TemplateManager
    return TemplateManager(templates_dir="prompts")


def _make_usage_tracker():
    """Return a fresh UsageTracker."""
    from datamind.engine.usage import UsageTracker
    return UsageTracker()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoPhaseExecution:
    def test_auto_phase_executes_and_advances(self):
        """AUTO phase completes via LLM, state advances to next phase.

        With phases [AUTO, GATE, AUTO], run() processes the first AUTO phase
        then pauses at the GATE, returning WaitForApproval.
        """
        from datamind.engine.agent import DataMindAgent, WaitForApproval

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="Analysis complete.",
                model="mock",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            ),
        ])
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
        )

        result = agent.run(sm)

        # After processing "analyze" (AUTO), the next phase "gate-review" is
        # a GATE, so the loop pauses with WaitForApproval.
        assert isinstance(result, WaitForApproval)
        assert result.phase_id == "gate-review"
        # State advanced to the next phase (GATE)
        assert sm.state.phase == "gate-review"
        assert sm.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["gate-review"] == PhaseStatus.AWAITING_HUMAN.value
        # LLM was called exactly once
        assert mock_llm.call_count == 1


class TestGatePause:
    def test_gate_phase_pauses_with_wait_for_approval(self):
        """GATE phase yields WaitForApproval without calling the LLM."""
        from datamind.engine.agent import DataMindAgent, WaitForApproval

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        # Advance to the GATE phase
        sm.complete_phase("analyze")
        assert sm.state.phase == "gate-review"

        mock_llm = MockLLMClient()
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
        )

        result = agent.run(sm)

        assert isinstance(result, WaitForApproval)
        assert result.phase_id == "gate-review"
        assert result.phase_name == "Gate: Review"
        # LLM was NOT called (GATE pauses immediately)
        assert mock_llm.call_count == 0


class TestApproveGate:
    def test_approve_gate_resumes_execution(self):
        """approve_gate advances past GATE and continues through next AUTO phase."""
        from datamind.engine.agent import DataMindAgent, WaitForApproval, SkillComplete

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="Analysis done.",
                model="mock",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            ),
            LLMResponse(
                content="Execution done.",
                model="mock",
                usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            ),
        ])
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
        )

        # First run: processes "analyze", hits GATE "gate-review"
        result1 = agent.run(sm)
        assert isinstance(result1, WaitForApproval)
        assert result1.phase_id == "gate-review"

        # Approve the GATE — resumes and processes "execute", workflow complete
        result2 = agent.approve_gate({"approved": True})
        assert isinstance(result2, SkillComplete)
        assert result2.result == "pass"
        assert sm.state.phases["gate-review"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["execute"] == PhaseStatus.COMPLETE.value


class TestToolCalls:
    def test_llm_tool_calls_are_executed(self):
        """Tool calls in the LLM response are dispatched via ToolRegistry.

        Uses [AUTO, GATE, AUTO] phases so the first AUTO phase processes
        tool calls, then the loop pauses at the GATE.
        """
        from datamind.engine.agent import DataMindAgent, WaitForApproval
        from datamind.engine.tools import ToolRegistry

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    {"id": "call_1", "type": "function", "name": "search", "arguments": '{"q": "test"}'},
                ],
                model="mock",
                finish_reason="tool_calls",
                usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            ),
            LLMResponse(
                content="Found results for test query.",
                model="mock",
                finish_reason="stop",
                usage={"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
            ),
        ])

        tool_calls_executed = []

        def search_handler(q=None):
            tool_calls_executed.append({"name": "search", "q": q})
            return {"content": "Result for search: found 3 items"}

        registry = ToolRegistry()
        registry.register("search", {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search tool",
                "parameters": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            },
        }, search_handler)

        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
            tool_registry=registry,
        )

        result = agent.run(sm)

        # After processing "analyze" (AUTO), hits GATE "gate-review"
        assert isinstance(result, WaitForApproval)
        assert result.phase_id == "gate-review"
        assert len(tool_calls_executed) == 1
        assert tool_calls_executed[0]["name"] == "search"
        # Two LLM calls: one for initial (with tool_calls), one after tool results
        assert mock_llm.call_count == 2
        # State advanced correctly
        assert sm.state.phases["analyze"] == PhaseStatus.COMPLETE.value


class TestMaxToolTurns:
    def test_max_tool_turns_limit(self):
        """Agent stops calling the LLM after 5 tool-turn iterations.

        Uses [AUTO, GATE, AUTO] phases. The first AUTO phase gets trapped
        in tool-call loop; after 5 tool turns the loop stops, the phase
        completes, and execution pauses at the GATE.
        """
        from datamind.engine.agent import DataMindAgent, WaitForApproval
        from datamind.engine.tools import ToolRegistry

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)

        # Each response returns tool_calls, forcing another turn
        responses = []
        for i in range(7):  # more than 5
            tool_call = [{"id": f"call_{i}", "type": "function", "name": "search", "arguments": "{}"}]
            responses.append(LLMResponse(
                content="",
                tool_calls=tool_call,
                model="mock",
                finish_reason="tool_calls",
                usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            ))

        mock_llm = MockLLMClient(responses=responses)

        registry = ToolRegistry()
        registry.register("search", {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search tool",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }, lambda: {"content": "mock result"})

        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
            tool_registry=registry,
        )

        result = agent.run(sm)

        # Should stop after 1 initial + 5 tool turns = 6 total LLM calls
        assert mock_llm.call_count == 6
        # After the tool-call loop, the phase completes and we hit the GATE
        assert isinstance(result, WaitForApproval)
        assert result.phase_id == "gate-review"


class TestContextAssembly:
    def test_context_assembly_from_artifacts(self):
        """Agent assembles context from active artifacts of completed phases.

        Starts at the last AUTO phase ("execute") with prior artifacts from
        "analyze".  After "execute" completes the workflow is done, so run()
        returns SkillComplete.  We verify context assembly by inspecting the
        system prompt sent to the LLM.
        """
        from datamind.engine.agent import DataMindAgent, SkillComplete

        # Start at the second AUTO phase with prior artifacts
        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        sm.complete_phase("analyze", artifact_path="phase-1-analyze.md")
        sm.approve_gate("gate-review", decision={"approved": True})
        # Now at "execute", with "analyze" as a prior artifact
        assert sm.state.phase == "execute"

        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="Executing with prior context.",
                model="mock",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            ),
        ])
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=_make_usage_tracker(),
        )

        result = agent.run(sm)

        # Last phase completed, workflow is done
        assert isinstance(result, SkillComplete)
        assert result.result == "pass"
        # Verify the LLM received context including the prior artifact
        system_message = mock_llm.calls[0]["messages"][0]["content"]
        assert "phase-1-analyze.md" in system_message


class TestUsageTracking:
    def test_usage_tracking_after_llm_call(self):
        """usage_tracker.record() is called after each LLM call.

        Uses [AUTO, GATE, AUTO].  The first AUTO phase calls the LLM once,
        usage is recorded, then the loop pauses at the GATE.
        """
        from datamind.engine.agent import DataMindAgent, WaitForApproval

        sm = _make_sm(AUTO_GATE_AUTO_PHASES)
        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="Response with usage.",
                model="mock-model",
                usage={"prompt_tokens": 42, "completion_tokens": 7, "total_tokens": 49},
            ),
        ])
        tracker = _make_usage_tracker()
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=tracker,
        )

        result = agent.run(sm)

        # Hit GATE after first AUTO phase
        assert isinstance(result, WaitForApproval)
        assert result.phase_id == "gate-review"
        assert tracker.prompt_tokens == 42
        assert tracker.completion_tokens == 7
        assert tracker.total_tokens == 49


class TestFullWorkflow:
    def test_full_workflow_through_all_phases(self):
        """End-to-end: run through all phases with GATE pauses and approvals."""
        from datamind.engine.agent import (
            DataMindAgent,
            WaitForApproval,
            SkillComplete,
        )

        sm = _make_sm(FULL_WORKFLOW_PHASES)

        # Pre-built responses for each AUTO phase
        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="I understand the request.",
                model="mock",
                usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            ),
            LLMResponse(
                content="Executing the plan.",
                model="mock",
                usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            ),
            LLMResponse(
                content="Delivering results.",
                model="mock",
                usage={"prompt_tokens": 6, "completion_tokens": 3, "total_tokens": 9},
            ),
        ])
        tracker = _make_usage_tracker()
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=_make_prompt_manager(),
            usage_tracker=tracker,
        )

        # Step 1: run() — should process "understand" (AUTO), then hit "gate-plan" (GATE)
        r1 = agent.run(sm)
        assert isinstance(r1, WaitForApproval)
        assert r1.phase_id == "gate-plan"
        assert sm.state.phases["understand"] == PhaseStatus.COMPLETE.value

        # Step 2: approve_gate("gate-plan") — should approve, process "execute" (AUTO),
        # then hit "gate-result" (GATE)
        r2 = agent.approve_gate({"plan_approved": True})
        assert isinstance(r2, WaitForApproval)
        assert r2.phase_id == "gate-result"
        assert sm.state.phases["gate-plan"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["execute"] == PhaseStatus.COMPLETE.value

        # Step 3: approve_gate("gate-result") — should approve, process "deliver" (AUTO),
        # then complete the workflow
        r3 = agent.approve_gate({"result_signed_off": True})
        assert isinstance(r3, SkillComplete)
        assert r3.result == "pass"
        assert sm.state.phases["gate-result"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["deliver"] == PhaseStatus.COMPLETE.value
        assert sm.state.result == "pass"
        assert sm.state.completed_at is not None

        # All 3 AUTO phases consumed 3 LLM responses
        assert mock_llm.call_count == 3
        # Usage recorded for all 3 calls
        assert tracker.total_tokens == 13 + 12 + 9
