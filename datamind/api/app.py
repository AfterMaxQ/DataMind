"""FastAPI REST API for DataMind Studio Web UI."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datamind.engine.project import Project


class RegisterDatasetRequest(BaseModel):
    file_path: str


class DecisionRequest(BaseModel):
    what: str
    why: str
    alternatives: list[str] = []


def create_app(project_root: str) -> FastAPI:
    app = FastAPI(title="DataMind Studio API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/datasets")
    def list_datasets():
        proj = Project(project_root)
        datasets = proj.graph.list_nodes_by_type("dataset")
        return [{"id": d["id"], "name": d["name"], "path": d.get("path"), "created_at": d["created_at"]} for d in datasets]

    @app.post("/datasets/register")
    def register_dataset(req: RegisterDatasetRequest):
        proj = Project(project_root)
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
        proj = Project(project_root)
        return {"content": tool_read_context(proj)}

    @app.post("/decisions")
    def log_decision(req: DecisionRequest):
        proj = Project(project_root)
        result = proj.cognition.log_decision(what=req.what, why=req.why, alternatives=req.alternatives)
        return {"id": result}

    @app.get("/decisions")
    def list_decisions(limit: int = 10):
        proj = Project(project_root)
        return proj.cognition.get_recent_decisions(limit)

    @app.get("/skills")
    def list_skills():
        proj = Project(project_root)
        return proj.skills.list_skills()

    @app.get("/lineage/{dataset_id}")
    def get_lineage(dataset_id: str):
        proj = Project(project_root)
        node = proj.graph.get_node(dataset_id)
        if not node:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return {"dataset": node, "ancestors": proj.lineage.query_ancestors(dataset_id), "descendants": proj.lineage.query_descendants(dataset_id)}

    return app
