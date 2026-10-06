from typing import Dict, List, Optional
from app.models.domain import AgentRegistration, AgentStatus
from app.db import db

class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}
        # Load saved agents from SQLite Database
        for aid, data in db.get_all_agents().items():
            self._agents[aid] = AgentRegistration(**data)

    def register_agent(self, agent: AgentRegistration) -> AgentRegistration:
        if len(self._agents) >= 10 and agent.agent_id not in self._agents:
            raise ValueError("Maximum limit of 10 agents reached. Cannot register more agents.")
        self._agents[agent.agent_id] = agent
        db.save_agent(agent.agent_id, agent.model_dump())
        return agent

    def update_agent(self, agent_id: str, updates: dict) -> Optional[AgentRegistration]:
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            updated_data = agent.model_dump()
            updated_data.update(updates)
            new_agent = AgentRegistration(**updated_data)
            self._agents[agent_id] = new_agent
            db.save_agent(agent_id, new_agent.model_dump())
            return new_agent
        return None

    def remove_agent(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            db.delete_agent(agent_id)
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        return self._agents.get(agent_id)

    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentRegistration]:
        if status:
            return [a for a in self._agents.values() if a.status == status]
        return list(self._agents.values())

agent_registry = AgentRegistry()
