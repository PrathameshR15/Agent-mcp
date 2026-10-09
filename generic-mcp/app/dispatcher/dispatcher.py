import asyncio
from typing import Dict, Any, List
from app.models.domain import Job, AgentRegistration, JobStatus
from app.adapters.base import BaseAgentAdapter
from app.adapters.mock_agents import (
    MockPotholeAgentAdapter, MockSpeedLimitAgentAdapter,
    MockTempAnomalyAgentAdapter, MockRadarAgentAdapter, MockLogAnalyzerAgentAdapter
)
import requests
from app.jobs.job_manager import JobManager

class GenericHttpAgentAdapter(BaseAgentAdapter):
    def __init__(self, endpoint: str, auth: tuple = None):
        self.endpoint = endpoint
        self.auth = auth

    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        def _make_req():
            try:
                import base64
                files = None
                
                # If the UI uploaded an image, we reconstruct it and attach it as a true file upload!
                if "image_base64" in data:
                    img_bytes = base64.b64decode(data.pop("image_base64"))
                    img_name = data.pop("image_name", "upload.jpg")
                    files = {"file": (img_name, img_bytes, "image/jpeg")} # The agent receives it as a 'file' parameter
                
                # Convert the remaining data payload into flat string key-value pairs for form-data
                form_data = {str(k): str(v) for k, v in data.items()}
                
                if files:
                    # Automatically sends as multipart/form-data
                    resp = requests.post(self.endpoint, data=form_data, files=files, timeout=15, auth=self.auth)
                else:
                    # Automatically sends as application/x-www-form-urlencoded
                    resp = requests.post(self.endpoint, data=form_data, timeout=15, auth=self.auth)
                    
                return resp.json()
            except Exception as e:
                return {"error": f"Failed to contact agent: {str(e)}"}
        return await asyncio.to_thread(_make_req)
        
    async def health_check(self) -> bool:
        return True
        
    def get_capabilities(self) -> List[str]:
        return []

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
            
            # If no hardcoded adapter, dynamically build one from the agent's endpoint URL!
            if not adapter and agent.endpoint and agent.endpoint.startswith("http"):
                auth_tuple = None
                if agent.metadata and "username" in agent.metadata and "password" in agent.metadata:
                    auth_tuple = (agent.metadata["username"], agent.metadata["password"])
                
                adapter = GenericHttpAgentAdapter(agent.endpoint, auth=auth_tuple)
                
            if adapter:
                tasks.append(self._execute_agent_task(job.job_id, agent.agent_id, adapter, job.request.payload))
            else:
                self.job_manager.add_result(job.job_id, agent.agent_id, {"error": "Adapter not found for agent and no valid endpoint provided."})
                
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
