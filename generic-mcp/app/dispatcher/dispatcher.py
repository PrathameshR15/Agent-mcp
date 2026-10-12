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
    def __init__(self, endpoint: str, auth: tuple = None, headers: dict = None, agent_name: str = "Agent"):
        self.endpoint = endpoint
        self.auth = auth
        self.headers = headers or {}
        self.agent_name = agent_name

    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        def _make_req():
            try:
                import base64
                import json
                files = None
                
                payload_data = dict(data)
                
                # If the UI uploaded an image, we reconstruct it and attach it as a file upload!
                if "image_base64" in payload_data:
                    img_bytes = base64.b64decode(payload_data.pop("image_base64"))
                    img_name = payload_data.pop("image_name", "upload.jpg")
                    files = {"file": (img_name, img_bytes, "image/jpeg")}
                
                print(f"[{job_id}] Receiver: {self.agent_name} ({self.endpoint})")
                print(f"[{job_id}] Forwarding payload: {payload_data}")
                
                # Specialized format for Discord webhooks
                if "discord.com/api/webhooks" in self.endpoint:
                    discord_text = f"🚨 **Agent Alert Dispatched** [{job_id}]\n**Agent:** {self.agent_name}\n```json\n{json.dumps(payload_data, indent=2)}\n```"
                    resp = requests.post(self.endpoint, json={"content": discord_text}, timeout=15)
                    if resp.status_code in [200, 204]:
                        return {"status": "success", "message": "Alert delivered to Discord webhook"}
                    try:
                        return resp.json()
                    except Exception:
                        return {"status": "error", "code": resp.status_code, "text": resp.text}

                # If file is attached, send as multipart/form-data
                if files:
                    form_data = {str(k): str(v) for k, v in payload_data.items()}
                    resp = requests.post(self.endpoint, data=form_data, files=files, headers=self.headers, timeout=15, auth=self.auth)
                else:
                    # Send as true application/json for modern webhooks/APIs
                    resp = requests.post(self.endpoint, json=payload_data, headers=self.headers, timeout=15, auth=self.auth)
                    
                if resp.status_code in [200, 201, 204]:
                    try:
                        return resp.json()
                    except Exception:
                        return {"status": "success", "response": resp.text or "OK"}
                else:
                    try:
                        return resp.json()
                    except Exception:
                        return {"status": "error", "code": resp.status_code, "response": resp.text}
            except Exception as e:
                return {"error": f"Failed to contact agent: {str(e)}"}
        return await asyncio.to_thread(_make_req)
        
    async def health_check(self) -> bool:
        def _ping():
            try:
                resp = requests.get(self.endpoint, headers=self.headers, auth=self.auth, timeout=3)
                return resp.status_code < 500
            except Exception:
                return False
        return await asyncio.to_thread(_ping)
        
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
                headers = {}
                if agent.metadata:
                    if "username" in agent.metadata and "password" in agent.metadata:
                        auth_tuple = (agent.metadata["username"], agent.metadata["password"])
                    if "auth_header" in agent.metadata and agent.metadata["auth_header"]:
                        raw_auth = str(agent.metadata["auth_header"]).strip()
                        if not raw_auth.lower().startswith("bearer ") and not raw_auth.lower().startswith("apikey "):
                            headers["Authorization"] = f"Bearer {raw_auth}"
                        else:
                            headers["Authorization"] = raw_auth
                
                adapter = GenericHttpAgentAdapter(agent.endpoint, auth=auth_tuple, headers=headers, agent_name=agent.name)
                
            if adapter:
                tasks.append(self._execute_agent_task(job.job_id, agent, adapter, job.request.payload))
            else:
                self.job_manager.add_result(job.job_id, agent.agent_id, {"error": "Adapter not found for agent and no valid endpoint provided."})
                
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    pass
                    
        # Check if all completed
        self.job_manager.update_job_status(job.job_id, JobStatus.COMPLETED)

    async def _execute_agent_task(self, job_id: str, agent: AgentRegistration, adapter: BaseAgentAdapter, payload: Dict[str, Any]):
        try:
            agent_id = agent.agent_id
            agent_name = agent.name
            # Pre-flight check: ensure agent is alive before sending payload
            if hasattr(adapter, "health_check"):
                is_alive = await adapter.health_check()
                if not is_alive:
                    endpoint_desc = getattr(adapter, 'endpoint', 'endpoint')
                    print(f"[{job_id}] Agent '{agent_name}' (ID: {agent_id}, URL: {endpoint_desc}) is OFFLINE. Skipping dead link.")
                    self.job_manager.add_result(job_id, agent_id, {"error": f"Agent '{agent_name}' is OFFLINE or tunnel is unreachable."})
                    return

            print(f"[{job_id}] Selected Agent: '{agent_name}' (ID: {agent_id})")
            result = await asyncio.wait_for(adapter.process(job_id, payload), timeout=30.0)
            self.job_manager.add_result(job_id, agent_id, result)
        except asyncio.TimeoutError:
            self.job_manager.add_result(job_id, agent.agent_id, {"error": f"Agent '{agent.name}' processing timed out"})
        except Exception as e:
            self.job_manager.add_result(job_id, agent.agent_id, {"error": str(e)})
