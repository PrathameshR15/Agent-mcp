from typing import Dict, List, Optional
from app.models.domain import AgentRegistration, AgentStatus

class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}

    def register_agent(self, agent: AgentRegistration) -> AgentRegistration:
        self._agents[agent.agent_id] = agent
        return agent

    def update_agent(self, agent_id: str, updates: dict) -> Optional[AgentRegistration]:
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            updated_data = agent.model_dump()
            updated_data.update(updates)
            self._agents[agent_id] = AgentRegistration(**updated_data)
            return self._agents[agent_id]
        return None

    def remove_agent(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        return self._agents.get(agent_id)

    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentRegistration]:
        if status:
            return [a for a in self._agents.values() if a.status == status]
        return list(self._agents.values())

agent_registry = AgentRegistry()
