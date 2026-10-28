"""In-process background job manager for pipeline runs.

A minimal, dependency-free job queue: jobs are submitted as coroutine factories
and run on the event loop, with their status and result tracked in memory. A
production deployment would swap this for a persistent queue (e.g. Redis +
Celery / RQ); the ``Job``/``JobManager`` interface keeps that swap local.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

CoroutineFactory = Callable[[], Awaitable[Any]]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    run_id: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "run_id": self.run_id,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._counter = 0

    def submit(self, run_id: str, factory: CoroutineFactory) -> Job:
        self._counter += 1
        job_id = f"job-{self._counter:04d}"
        job = Job(job_id=job_id, run_id=run_id)
        self._jobs[job_id] = job
        asyncio.create_task(self._run(job, factory))
        return job

    async def _run(self, job: Job, factory: CoroutineFactory) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        try:
            job.result = await factory()
            job.status = JobStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 - recorded on the job, not swallowed
            job.error = str(exc)
            job.status = JobStatus.FAILED
        finally:
            job.finished_at = time.time()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())
