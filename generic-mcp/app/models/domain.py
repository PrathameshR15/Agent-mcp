from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
from datetime import datetime

class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNHEALTHY = "unhealthy"

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentCapability(BaseModel):
    name: str
    description: str

class AgentRegistration(BaseModel):
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    input_types: List[str]
    output_types: List[str]
    endpoint: str
    version: str
    status: AgentStatus = AgentStatus.ACTIVE
    priority: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class JobRequest(BaseModel):
    data_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_type: str
    payload: Dict[str, Any]
    requirements: List[str]

class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request: JobRequest
    status: JobStatus = JobStatus.PENDING
    assigned_agents: List[str] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
