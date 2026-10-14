import asyncio
import os
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request

# Load .env if present
for env_candidate in [Path(".env"), Path("../.env")]:
    if env_candidate.exists():
        with open(env_candidate, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        break

from app.models.domain import AgentRegistration, JobRequest, Job, AgentStatus
from app.registry.agent_registry import agent_registry
from app.routing.router import Router
from app.jobs.job_manager import job_manager
from app.ingestion.ingestor import ingestor
from app.dispatcher.dispatcher import AgentDispatcher

app = FastAPI(title="Generic Multi-Agent MCP Platform")

job_queue = asyncio.Queue()

async def job_worker():
    while True:
        job, matching_agents = await job_queue.get()
        try:
            await dispatcher.dispatch_job(job, matching_agents)
        except Exception as e:
            print(f"Job dispatch error: {e}")
        finally:
            job_queue.task_done()

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=FileResponse)
async def admin_dashboard():
    return "app/static/admin.html"

# MCP Server
mcp = FastMCP("generic-mcp-platform")
router = Router(agent_registry)
dispatcher = AgentDispatcher(job_manager)
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(job_worker())
    # Synchronize all registered agents' capabilities into the semantic model
    for agent in agent_registry.list_agents():
        for cap in agent.capabilities:
            if cap:
                desc = agent.description or f"handles {cap.replace('_', ' ')}"
                ingestor.register_capability(cap.strip(), desc)

app.mount("/mcp", mcp.sse_app())
# ----- MCP Platform API -----

class StartPollingRequest(BaseModel):
    api_url: str
    login_id: str
    password: str
    interval_seconds: int = 10
    requirements: List[str] = []

active_pollers = {}

async def poll_service_task(poller_id: str, req: StartPollingRequest):
    while poller_id in active_pollers:
        try:
            headers = {}
            auth = None
            if req.login_id and req.login_id.lower() == "bearer":
                headers["Authorization"] = f"Bearer {req.password}"
            elif req.password and (req.password.startswith("ey") or req.login_id.lower() in ["none", ""]):
                headers["Authorization"] = f"Bearer {req.password}"
            elif req.login_id and req.login_id.lower() != "none" and req.password:
                auth = (req.login_id, req.password)
            
            resp = await asyncio.to_thread(requests.get, req.api_url, auth=auth, headers=headers, timeout=10)
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {"content": resp.text}
                
                print(f"[Polling {poller_id}] Successfully fetched data from {req.api_url}")
                job_req = ingestor.process_input("application/json", payload, req.requirements)
                matching_agents = router.find_matching_agents(job_req)
                if matching_agents:
                    job = job_manager.create_job(job_req)
                    job_queue.put_nowait((job, matching_agents))
                    print(f"[Polling {poller_id}] Created job {job.job_id} assigned to agents: {[a.agent_id for a in matching_agents]}")
                else:
                    print(f"[Polling {poller_id}] WARNING: Data fetched but NO MATCHING AGENTS found for requirements {req.requirements}!")
            else:
                print(f"[Polling {poller_id}] Failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[Polling {poller_id}] Error: {e}")
        
        await asyncio.sleep(req.interval_seconds)

@app.post("/api/polling/start")
async def start_polling(request: StartPollingRequest):
    import uuid
    poller_id = str(uuid.uuid4())
    task = asyncio.create_task(poll_service_task(poller_id, request))
    active_pollers[poller_id] = task
    return {"status": "started", "poller_id": poller_id}

@app.post("/api/polling/stop/{poller_id}")
async def stop_polling(poller_id: str):
    if poller_id in active_pollers:
        active_pollers[poller_id].cancel()
        del active_pollers[poller_id]
        return {"status": "stopped", "poller_id": poller_id}
    raise HTTPException(status_code=404, detail="Poller not found")

class SubmitDataRequest(BaseModel):
    data_type: str
    payload: Dict[str, Any]
    requirements: List[str]

class SubmitFetchRequest(BaseModel):
    data_type: str
    api_url: str
    requirements: List[str]
    # optional authentication for secure endpoints
    username: Optional[str] = None
    password: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

@app.get("/api/submit")
async def submit_data_info():
    return {"message": "POST JSON data to /api/submit to ingest and route events to agents."}

@app.post("/api/submit")
async def submit_data(raw_request: Request, background_tasks: BackgroundTasks):
    try:
        body = await raw_request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Expected valid JSON body")

    # If caller wrapped it in {"payload": ..., "data_type": ...}
    if isinstance(body, dict) and "payload" in body and isinstance(body.get("payload"), dict):
        data_type = body.get("data_type", "application/json")
        payload = body["payload"]
        requirements = body.get("requirements", [])
    elif isinstance(body, dict):
        # Caller posted raw alert data directly
        data_type = "application/json"
        payload = body
        requirements = []
    elif isinstance(body, list):
        data_type = "application/json"
        payload = {"items": body}
        requirements = []
    else:
        data_type = "application/json"
        payload = {"content": str(body)}
        requirements = []

    job_req = ingestor.process_input(data_type, payload, requirements)
    
    # Route to agents
    matching_agents = router.find_matching_agents(job_req)
    if not matching_agents:
        raise HTTPException(status_code=400, detail="No matching agents found for requirements")
        
    # Create job
    job = job_manager.create_job(job_req)
    
    # Push to Queue
    job_queue.put_nowait((job, matching_agents))
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "assigned_agents": [a.agent_id for a in matching_agents],
        "assigned_agent_details": [{"agent_id": a.agent_id, "name": a.name} for a in matching_agents]
    }

@app.post("/api/submit_fetch")
async def submit_fetch(request: SubmitFetchRequest, background_tasks: BackgroundTasks):
    try:
        headers = request.headers or {}
        auth = None
        if request.username and request.username.lower() == "bearer":
            headers["Authorization"] = f"Bearer {request.password}"
        elif request.password and (request.password.startswith("ey") or (request.username and request.username.lower() in ["none", ""])):
            headers["Authorization"] = f"Bearer {request.password}"
        elif request.username and request.password:
            auth = (request.username, request.password)

        response = requests.get(request.api_url, timeout=10, auth=auth, headers=headers)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            # If not JSON, just wrap the text in a payload
            payload = {"content": response.text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data from API: {str(e)}")

    job_req = ingestor.process_input(request.data_type, payload, request.requirements)
    
    # Route to agents
    matching_agents = router.find_matching_agents(job_req)
    if not matching_agents:
        raise HTTPException(status_code=400, detail="No matching agents found for requirements")
        
    # Create job
    job = job_manager.create_job(job_req)
    
    # Push to Queue
    job_queue.put_nowait((job, matching_agents))
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "assigned_agents": [a.agent_id for a in matching_agents],
        "assigned_agent_details": [{"agent_id": a.agent_id, "name": a.name} for a in matching_agents]
    }

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/agents")
async def list_agents():
    agents = agent_registry.list_agents()
    return [a for a in agents if a.agent_id != "civic-data-agent-01"]

@app.get("/api/agents/health")
async def check_agents_health():
    agents = agent_registry.list_agents()
    agents_to_check = [a for a in agents if a.agent_id != "civic-data-agent-01"]

    async def _check_single(agent: AgentRegistration):
        if not agent.endpoint or not agent.endpoint.startswith("http") or agent.endpoint == "http://mock-endpoint":
            return {"agent_id": agent.agent_id, "healthy": True, "status": "online", "details": "Internal Service"}

        headers = {}
        auth = None
        if agent.metadata:
            if "username" in agent.metadata and "password" in agent.metadata:
                auth = (agent.metadata["username"], agent.metadata["password"])
            if "auth_header" in agent.metadata and agent.metadata["auth_header"]:
                raw_auth = str(agent.metadata["auth_header"]).strip()
                if not raw_auth.lower().startswith("bearer ") and not raw_auth.lower().startswith("apikey "):
                    headers["Authorization"] = f"Bearer {raw_auth}"
                else:
                    headers["Authorization"] = raw_auth

        def _ping():
            try:
                resp = requests.get(agent.endpoint, headers=headers, auth=auth, timeout=3)
                is_online = resp.status_code < 500
                return {
                    "agent_id": agent.agent_id,
                    "healthy": is_online,
                    "status": "online" if is_online else "offline",
                    "details": f"HTTP {resp.status_code}" if is_online else f"HTTP {resp.status_code} (Down)"
                }
            except requests.exceptions.Timeout:
                return {"agent_id": agent.agent_id, "healthy": False, "status": "offline", "details": "Timeout"}
            except Exception as e:
                return {"agent_id": agent.agent_id, "healthy": False, "status": "offline", "details": "Unreachable"}

        return await asyncio.to_thread(_ping)

    health_results = await asyncio.gather(*[_check_single(a) for a in agents_to_check])
    return {item["agent_id"]: item for item in health_results}

@app.post("/api/agents")
async def register_new_agent(agent: AgentRegistration):
    try:
        agent_registry.register_agent(agent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    for cap in agent.capabilities:
        if cap:
            desc = agent.description or f"handles {cap.replace('_', ' ')}"
            ingestor.register_capability(cap.strip(), desc)
    return {"status": "success", "agent_id": agent.agent_id}

class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None
    input_types: Optional[List[str]] = None
    output_types: Optional[List[str]] = None
    endpoint: Optional[str] = None
    version: Optional[str] = None
    status: Optional[AgentStatus] = None
    priority: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/api/agents/{agent_id}")
async def update_agent_endpoint(agent_id: str, updates: UpdateAgentRequest):
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    updated_agent = agent_registry.update_agent(agent_id, update_data)
    if not updated_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if updated_agent.capabilities:
        for cap in updated_agent.capabilities:
            if cap:
                desc = updated_agent.description or f"handles {cap.replace('_', ' ')}"
                ingestor.register_capability(cap.strip(), desc)

    return {"status": "success", "agent": updated_agent}

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    success = agent_registry.remove_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "success", "agent_id": agent_id}

# Register MCP Tools
@mcp.tool()
async def submit_job(data_type: str, payload: dict, requirements: list) -> str:
    """Submit a new job to the platform. Returns the job_id."""
    job_req = ingestor.process_input(data_type, payload, requirements)
    matching_agents = router.find_matching_agents(job_req)
    if not matching_agents:
        return "Error: No matching agents found."
    job = job_manager.create_job(job_req)
    job_queue.put_nowait((job, matching_agents))
    return f"Job {job.job_id} created and queued."

@mcp.tool()
async def check_job(job_id: str) -> str:
    """Check the status and results of a job."""
    job = job_manager.get_job(job_id)
    if not job:
        return "Error: Job not found."
    return f"Status: {job.status}. Results: {job.results}"

@mcp.tool()
async def get_camera_alert(alertId: str, userToken: str) -> str:
    """Fetch details of a camera alert from Avinyx platform by its alert ID"""
    import json
    try:
        base_url = os.getenv("CLOUDFLARE_ALERTS_API", "https://chancellor-pirates-may-digit.trycloudflare.com/alerts").rstrip("/")
        url = f"{base_url}/{alertId}"
        headers = {
            "Authorization": f"Bearer {userToken}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return f"Failed to fetch alert: {str(e)}"





