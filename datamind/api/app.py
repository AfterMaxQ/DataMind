"""FastAPI REST API for DataMind Studio Web UI."""

import json
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from datamind.engine.project import Project

_log = logging.getLogger(__name__)


class RegisterDatasetRequest(BaseModel):
    file_path: str


class DecisionRequest(BaseModel):
    what: str
    why: str
    alternatives: list[str] = []


class SwitchModelRequest(BaseModel):
    model: str


class GateDecisionRequest(BaseModel):
    session_dir: str
    decision: dict


def create_app(project_root: str) -> FastAPI:
    app = FastAPI(title="DataMind Studio API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # Singleton Project instance — cached on app.state so mutations
    # (e.g. model switch) persist across requests.
    app.state.project = Project(project_root)

    def _proj():
        """Return the cached Project singleton from app state."""
        return app.state.project

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/datasets")
    def list_datasets():
        proj = _proj()
        datasets = proj.graph.list_nodes_by_type("dataset")
        return [{"id": d["id"], "name": d["name"], "path": d.get("path"), "created_at": d["created_at"]} for d in datasets]

    @app.post("/datasets/register")
    def register_dataset(req: RegisterDatasetRequest):
        proj = _proj()
        try:
            node_id = proj.lineage.register_dataset(req.file_path)
            node = proj.graph.get_node(node_id)
            return node
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/context")
    def get_context():
        from datamind.mcp.server import tool_read_context
        proj = _proj()
        return {"content": tool_read_context(proj)}

    @app.post("/decisions")
    def log_decision(req: DecisionRequest):
        proj = _proj()
        result = proj.cognition.log_decision(what=req.what, why=req.why, alternatives=req.alternatives)
        return {"id": result}

    @app.get("/decisions")
    def list_decisions(limit: int = 10):
        proj = _proj()
        return proj.cognition.get_recent_decisions(limit)

    @app.get("/skills")
    def list_skills():
        proj = _proj()
        return proj.skills.list_skills()

    @app.get("/lineage/{dataset_id}")
    def get_lineage(dataset_id: str):
        proj = _proj()
        node = proj.graph.get_node(dataset_id)
        if not node:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return {"dataset": node, "ancestors": proj.lineage.query_ancestors(dataset_id), "descendants": proj.lineage.query_descendants(dataset_id)}

    # ------------------------------------------------------------------
    # v2 endpoints
    # ------------------------------------------------------------------

    @app.get("/models")
    def list_models():
        proj = _proj()
        try:
            return {"models": proj.llm_client.list_models(), "active": proj.llm_client.model}
        except Exception as exc:
            return {"models": [proj.llm_client.model], "active": proj.llm_client.model, "error": str(exc)}

    @app.post("/models/switch")
    def switch_model(req: SwitchModelRequest):
        proj = _proj()
        available = proj.llm_client.list_models()
        if req.model not in available:
            raise HTTPException(status_code=400, detail=f"Model '{req.model}' not available. Available: {available}")
        proj.llm_client.model = req.model
        return {"active": req.model}

    @app.get("/chat/stream")
    async def chat_stream(
        message: str = Query(..., description="User message"),
        skill: str | None = Query(None, description="Optional skill name"),
        target: str | None = Query(None, description="Optional target path"),
    ):
        proj = _proj()

        async def event_generator():
            try:
                # Build system prompt from skill context if provided
                system_prompt = proj.prompt_manager.render("data-scientist", {
                    "context": f"Skill: {skill}" if skill else "General chat",
                    "skills": proj.skills.list_skills() if not skill else skill,
                })

                messages: list[dict] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]

                # Stream LLM responses
                stream = proj.llm_client.chat(messages=messages, stream=True)
                accumulated = ""
                for chunk in stream:
                    delta = chunk.content if hasattr(chunk, "content") else ""
                    if delta:
                        accumulated += delta
                        yield {"event": "token", "data": json.dumps({"content": delta})}

                    # Record usage from the final chunk
                    if chunk.usage:
                        proj.usage_tracker.record(
                            prompt_tokens=chunk.usage.get("prompt_tokens", 0),
                            completion_tokens=chunk.usage.get("completion_tokens", 0),
                            model=chunk.model or proj.llm_client.model,
                        )

                yield {"event": "done", "data": json.dumps({"content": accumulated})}

            except Exception as exc:
                _log.exception("Chat stream error")
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}

        return EventSourceResponse(event_generator())

    @app.get("/skill-sessions")
    def list_skill_sessions():
        proj = _proj()
        sessions_dir = proj.paths["data_dir"]
        if sessions_dir is None:
            return {"sessions": []}
        import os
        sessions: list[dict] = []
        if os.path.isdir(sessions_dir):
            for entry in os.listdir(sessions_dir):
                full = os.path.join(sessions_dir, entry)
                if os.path.isdir(full) and os.path.exists(os.path.join(full, ".skill.yaml")):
                    try:
                        from datamind.engine.skill_state import SkillStateMachine
                        sm = SkillStateMachine.load(os.path.join(full, ".skill.yaml"))
                        sessions.append({
                            "session_id": sm.state.session,
                            "skill": sm.state.skill,
                            "target": sm.state.target,
                            "phase": sm.state.phase,
                            "result": sm.state.result,
                        })
                    except Exception:
                        sessions.append({"session_id": entry, "skill": "unknown", "error": "failed to load"})
        return {"sessions": sessions}

    @app.post("/skill/gate")
    def gate_decision(req: GateDecisionRequest):
        try:
            from datamind.engine.skill_state import SkillStateMachine
            from datamind.engine.agent import DataMindAgent, WaitForApproval, SkillComplete, AgentError

            yaml_path = req.session_dir + "/.skill.yaml" if not req.session_dir.endswith(".skill.yaml") else req.session_dir
            sm = SkillStateMachine.load(yaml_path)
            next_phase = sm.approve_gate(sm.state.phase, req.decision)

            # If the next phase is AUTO, resume agent execution through it
            if next_phase and sm.get_current_phase().type == "AUTO":
                proj = _proj()
                agent = proj.create_agent()
                result = agent.run(sm)
                if isinstance(result, AgentError):
                    return {"phase": sm.state.phase, "result": sm.state.result,
                            "error": result.error_message}
                if isinstance(result, WaitForApproval):
                    return {"phase": sm.state.phase, "result": sm.state.result,
                            "gate": {"phase_id": result.phase_id,
                                     "phase_name": result.phase_name,
                                     "context": result.context_message}}
                if isinstance(result, SkillComplete):
                    return {"phase": "", "result": result.result,
                            "usage": result.usage}

            return {"phase": next_phase, "result": sm.state.result}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session not found: {req.session_dir}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/usage")
    def get_usage():
        proj = _proj()
        return proj.usage_tracker.export()

    return app
