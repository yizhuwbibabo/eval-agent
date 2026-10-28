"""HTTP service layer tests (offline)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from agentevalops.server.app import create_app
from agentevalops.server.jobs import JobManager, JobStatus


def test_job_manager_runs_coroutine() -> None:
    async def run():
        manager = JobManager()
        job = manager.submit("r1", lambda: _fake())
        await asyncio.sleep(0.05)
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"ok": True}
        assert manager.get(job.job_id) is job

    asyncio.run(run())


async def _fake() -> dict:
    return {"ok": True}


def test_job_manager_records_failure() -> None:
    async def run():
        manager = JobManager()

        async def boom():
            raise RuntimeError("boom")

        job = manager.submit("r2", boom)
        await asyncio.sleep(0.05)
        assert job.status == JobStatus.FAILED
        assert "boom" in (job.error or "")

    asyncio.run(run())


def test_health_and_behaviors_endpoints() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/behaviors").json()
    assert "tool_failure_recovery" in body["behaviors"]
