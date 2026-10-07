from typing import List, Dict, Any
from app.models.domain import JobRequest, AgentRegistration, AgentStatus
from app.registry.agent_registry import AgentRegistry

class Router:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def find_matching_agents(self, request: JobRequest) -> List[AgentRegistration]:
        matching_agents = []
        active_agents = self.registry.list_agents(status=AgentStatus.ACTIVE)
        
        for agent in active_agents:
            # Check input compatibility
            if request.data_type not in agent.input_types and "*" not in agent.input_types:
                continue
                
            # Check capabilities (If the agent has ANY of the requested capabilities, select it)
            has_capabilities = False
            for req in request.requirements:
                if req in agent.capabilities:
                    has_capabilities = True
                    break
                    
            if has_capabilities:
                matching_agents.append(agent)
                
        # Rank by priority (higher is better)
        matching_agents.sort(key=lambda x: x.priority, reverse=True)
        return matching_agents
