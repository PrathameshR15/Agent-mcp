from typing import Dict, Optional, List
from app.models.domain import Job, JobRequest, JobStatus

class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def create_job(self, request: JobRequest) -> Job:
        job = Job(request=request)
        self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
        
    def update_job_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.status = status
        return job

    def assign_agents(self, job_id: str, agent_ids: List[str]) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.assigned_agents = agent_ids
        return job

    def add_result(self, job_id: str, agent_id: str, result: dict) -> Optional[Job]:
        job = self.get_job(job_id)
        if job:
            job.results[agent_id] = result
        return job

job_manager = JobManager()
