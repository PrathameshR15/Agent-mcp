import asyncio
from typing import Dict, Any, List
from app.models.domain import Job, AgentRegistration, JobStatus
from app.adapters.base import BaseAgentAdapter
from app.adapters.mock_agents import (
    MockPotholeAgentAdapter, MockSpeedLimitAgentAdapter,
    MockTempAnomalyAgentAdapter, MockRadarAgentAdapter, MockLogAnalyzerAgentAdapter
)
from app.jobs.job_manager import JobManager

class AgentDispatcher:
    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager
        # In a real app, adapters would be loaded dynamically based on endpoint/type
        self.adapters: Dict[str, BaseAgentAdapter] = {
            "pothole-agent-01": MockPotholeAgentAdapter(),
            "speedlimit-agent-01": MockSpeedLimitAgentAdapter(),
            "temp-anomaly-01": MockTempAnomalyAgentAdapter(),
            "radar-agent-01": MockRadarAgentAdapter(),
            "log-analyzer-01": MockLogAnalyzerAgentAdapter()
        }

    async def dispatch_job(self, job: Job, agents: List[AgentRegistration]):
        self.job_manager.update_job_status(job.job_id, JobStatus.PROCESSING)
        self.job_manager.assign_agents(job.job_id, [a.agent_id for a in agents])
        
        tasks = []
        for agent in agents:
            adapter = self.adapters.get(agent.agent_id)
            if adapter:
                tasks.append(self._execute_agent_task(job.job_id, agent.agent_id, adapter, job.request.payload))
            else:
                self.job_manager.add_result(job.job_id, agent.agent_id, {"error": "Adapter not found for agent"})
                
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    # Handle exceptions
                    pass
                    
        # Check if all completed
        self.job_manager.update_job_status(job.job_id, JobStatus.COMPLETED)

    async def _execute_agent_task(self, job_id: str, agent_id: str, adapter: BaseAgentAdapter, payload: Dict[str, Any]):
        try:
            # Add timeout handling
            result = await asyncio.wait_for(adapter.process(job_id, payload), timeout=30.0)
            self.job_manager.add_result(job_id, agent_id, result)
        except asyncio.TimeoutError:
            self.job_manager.add_result(job_id, agent_id, {"error": "Agent processing timed out"})
        except Exception as e:
            self.job_manager.add_result(job_id, agent_id, {"error": str(e)})
