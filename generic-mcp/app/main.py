import asyncio
import requests
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request

from app.models.domain import AgentRegistration, JobRequest, Job
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

app.mount("/mcp", mcp.sse_app())
# ----- MCP Platform API -----

class StartPollingRequest(BaseModel):
    api_url: str
    login_id: str
    password: str
    interval_seconds: int = 10
    requirements: List[str]

active_pollers = {}

async def poll_service_task(poller_id: str, req: StartPollingRequest):
    while poller_id in active_pollers:
        try:
            if req.login_id and req.login_id.lower() != "none":
                auth = (req.login_id, req.password)
                resp = await asyncio.to_thread(requests.get, req.api_url, auth=auth, timeout=10)
            else:
                resp = await asyncio.to_thread(requests.get, req.api_url, timeout=10)
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

@app.post("/api/submit")
async def submit_data(request: SubmitDataRequest, background_tasks: BackgroundTasks):
    job_req = ingestor.process_input(request.data_type, request.payload, request.requirements)
    
    # Route to agents
    matching_agents = router.find_matching_agents(job_req)
    if not matching_agents:
        raise HTTPException(status_code=400, detail="No matching agents found for requirements")
        
    # Create job
    job = job_manager.create_job(job_req)
    
    # Push to Queue
    job_queue.put_nowait((job, matching_agents))
    
    return {"job_id": job.job_id, "status": job.status, "assigned_agents": [a.agent_id for a in matching_agents]}

@app.post("/api/submit_fetch")
async def submit_fetch(request: SubmitFetchRequest, background_tasks: BackgroundTasks):
    try:
        auth = (request.username, request.password) if request.username and request.password else None
        headers = request.headers or {}
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
    
    return {"job_id": job.job_id, "status": job.status, "assigned_agents": [a.agent_id for a in matching_agents]}

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

@app.post("/api/agents")
async def register_new_agent(agent: AgentRegistration):
    agent_registry.register_agent(agent)
    return {"status": "success", "agent_id": agent.agent_id}

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
        url = f"http://localhost:3010/api/v1/alerts/{alertId}"
        headers = {
            "Authorization": f"Bearer {userToken}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return f"Failed to fetch alert: {str(e)}"
