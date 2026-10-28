"""In-process background job manager for pipeline runs.

Jobs run on the event loop via asyncio tasks. When a store is provided, job
status transitions are persisted so the queue survives a process restart
(running jobs do not auto-resume, but terminal state and results are preserved).
A production deployment can swap this for Redis + Arq/RQ; the ``Job``/``JobStatus``
types and the persistence interface keep that swap local.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from agentevalops.schemas.jobs import Job, JobStatus

CoroutineFactory = Callable[[], Awaitable[Any]]


class JobManager:
    def __init__(self, store: Any | None = None) -> None:
        self.store = store
        self._jobs: dict[str, Job] = {}
        self._counter = 0

    def submit(self, run_id: str, factory: CoroutineFactory) -> Job:
        self._counter += 1
        job = Job(job_id=f"job-{self._counter:04d}", run_id=run_id)
        self._jobs[job.job_id] = job
        if self.store is not None:
            self.store.save_job(job)
        asyncio.create_task(self._run(job, factory))
        return job

    async def _run(self, job: Job, factory: CoroutineFactory) -> None:
        job.status = JobStatus.RUNNING
        self._persist(job)
        try:
            job.result = await factory()
            job.status = JobStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 - recorded on the job, not swallowed
            job.error = str(exc)
            job.status = JobStatus.FAILED
        finally:
            self._persist(job)

    def _persist(self, job: Job) -> None:
        if self.store is not None:
            self.store.save_job(job)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())
