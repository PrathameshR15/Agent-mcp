import asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request

from app.models.domain import AgentRegistration, JobRequest, Job
from app.registry.agent_registry import agent_registry
from app.routing.router import Router
from app.jobs.job_manager import job_manager
from app.ingestion.ingestor import ingestor
from app.dispatcher.dispatcher import AgentDispatcher

app = FastAPI(title="Generic Multi-Agent MCP Platform")

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=FileResponse)
async def admin_dashboard():
    return "app/static/admin.html"

# MCP Server
mcp = MCPServer("generic-mcp-platform")
router = Router(agent_registry)
dispatcher = AgentDispatcher(job_manager)
@app.on_event("startup")
async def startup_event():
    # Register mock agents for MVP
    pothole_agent = AgentRegistration(
        agent_id="pothole-agent-01",
        name="Pothole Detector",
        description="Detects potholes in images",
        capabilities=["detect_pothole"],
        input_types=["image/jpeg", "image/png"],
        output_types=["application/json"],
        endpoint="http://mock-pothole",
        version="1.0"
    )
    speedlimit_agent = AgentRegistration(
        agent_id="speedlimit-agent-01",
        name="Speed Limit Detector",
        description="Detects speed limit signs",
        capabilities=["detect_speed_limit"],
        input_types=["image/jpeg", "image/png"],
        output_types=["application/json"],
        endpoint="http://mock-speedlimit",
        version="1.0"
    )
    temp_agent = AgentRegistration(
        agent_id="temp-anomaly-01",
        name="Temperature Monitor",
        description="Analyzes temperature sensor data for anomalies",
        capabilities=["analyze_temperature"],
        input_types=["application/json"],
        output_types=["application/json"],
        endpoint="http://mock-temp",
        version="1.0"
    )
    radar_agent = AgentRegistration(
        agent_id="radar-agent-01",
        name="Radar Processor",
        description="Processes radar image scans for objects",
        capabilities=["process_radar"],
        input_types=["image/png"],
        output_types=["application/json"],
        endpoint="http://mock-radar",
        version="1.0"
    )
    log_agent = AgentRegistration(
        agent_id="log-analyzer-01",
        name="Batch Log Analyzer",
        description="Parses CSV logs for batch events",
        capabilities=["parse_logs"],
        input_types=["text/csv"],
        output_types=["application/json"],
        endpoint="http://mock-logs",
        version="1.0"
    )
    
    agent_registry.register_agent(pothole_agent)
    agent_registry.register_agent(speedlimit_agent)
    agent_registry.register_agent(temp_agent)
    agent_registry.register_agent(radar_agent)
    agent_registry.register_agent(log_agent)

app.mount("/mcp", mcp.sse_app())
# ----- MCP Platform API -----

class SubmitDataRequest(BaseModel):
    data_type: str
    payload: Dict[str, Any]
    requirements: List[str]

@app.post("/api/submit")
async def submit_data(request: SubmitDataRequest, background_tasks: BackgroundTasks):
    job_req = ingestor.process_input(request.data_type, request.payload, request.requirements)
    
    # Route to agents
    matching_agents = router.find_matching_agents(job_req)
    if not matching_agents:
        raise HTTPException(status_code=400, detail="No matching agents found for requirements")
        
    # Create job
    job = job_manager.create_job(job_req)
    
    # Dispatch asynchronously
    background_tasks.add_task(dispatcher.dispatch_job, job, matching_agents)
    
    return {"job_id": job.job_id, "status": job.status, "assigned_agents": [a.agent_id for a in matching_agents]}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/agents")
async def list_agents():
    return agent_registry.list_agents()

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
    asyncio.create_task(dispatcher.dispatch_job(job, matching_agents))
    return f"Job {job.job_id} created and dispatched."

@mcp.tool()
async def check_job(job_id: str) -> str:
    """Check the status and results of a job."""
    job = job_manager.get_job(job_id)
    if not job:
        return "Error: Job not found."
    return f"Status: {job.status}. Results: {job.results}"
