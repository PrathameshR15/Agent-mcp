from typing import Dict, Optional, List
from app.models.domain import Job, JobRequest, JobStatus
from app.db import db
import json

def _dump_job(job: Job):
    return json.loads(job.model_dump_json())

class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        # Load saved jobs from SQLite Database
        for jid, data in db.get_all_jobs().items():
            self._jobs[jid] = Job(**data)

    def create_job(self, request: JobRequest) -> Job:
        job = Job(request=request)
        self._jobs[job.job_id] = job
        db.save_job(job.job_id, _dump_job(job))
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
        
    def update_job_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.status = status
            db.save_job(job_id, _dump_job(job))
        return job

    def assign_agents(self, job_id: str, agent_ids: List[str]) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.assigned_agents = agent_ids
            db.save_job(job_id, _dump_job(job))
        return job

    def add_result(self, job_id: str, agent_id: str, result: dict) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.results[agent_id] = result
            db.save_job(job_id, _dump_job(job))
        return job

job_manager = JobManager()
