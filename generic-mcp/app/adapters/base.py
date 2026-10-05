from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseAgentAdapter(ABC):
    @abstractmethod
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the data/job and return results."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the agent is healthy."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return a list of capabilities for this agent."""
        pass
