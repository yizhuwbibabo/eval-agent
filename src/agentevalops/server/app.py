"""FastAPI service exposing the evaluation pipeline over HTTP.

Run with::

    uvicorn agentevalops.server.app:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health                  liveness probe
    GET  /behaviors               registered behavior ids
    POST /runs                    start a pipeline run (background job)
    GET  /runs                    list jobs
    GET  /runs/{job_id}           job status
    GET  /runs/{job_id}/report    report bundle paths once completed
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agentevalops.config.settings import EvalConfig, get_settings
from agentevalops.pipeline import Pipeline
from agentevalops.server.jobs import Job, JobManager, JobStatus


def _build_pipeline() -> Pipeline:
    settings = get_settings()
    settings.ensure_dirs()
    return Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=settings.database_url,
    )


class RunRequest(BaseModel):
    run_id: str
    config: EvalConfig


def create_app() -> FastAPI:
    app = FastAPI(title="AgentEvalOps", version="0.1.0")
    pipeline = _build_pipeline()
    manager = JobManager()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/behaviors")
    def behaviors() -> dict[str, list[str]]:
        return {"behaviors": pipeline.registry.ids()}

    @app.post("/runs", status_code=202)
    def start_run(req: RunRequest) -> dict[str, str]:
        def factory():
            return pipeline.full(req.config, req.run_id)

        job = manager.submit(req.run_id, factory)
        return {"job_id": job.job_id, "status": job.status.value}

    @app.get("/runs")
    def list_runs() -> list[dict]:
        return [j.to_dict() for j in manager.list()]

    def _job(job_id: str) -> Job:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"unknown job {job_id!r}")
        return job

    @app.get("/runs/{job_id}")
    def job_status(job_id: str) -> dict:
        return _job(job_id).to_dict()

    @app.get("/runs/{job_id}/report")
    def job_report(job_id: str) -> dict:
        job = _job(job_id)
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=409, detail=f"job is {job.status.value}, not completed")
        return job.result or {}

    return app


app = create_app()
