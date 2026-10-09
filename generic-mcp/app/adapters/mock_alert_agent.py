from app.adapters.base import BaseAgentAdapter
from typing import Dict, Any, List

class MockAlertAgentAdapter(BaseAgentAdapter):
    """Simple mock agent that pretends to process alert data.
       It just returns the alerts (if any) unchanged.
    """
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        # Assume the fetched alerts are under a key called "alerts"
        alerts = data.get("alerts", data)
        return {"status": "success", "alerts": alerts}

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        # The capability name that the router will match against
        return ["process_alert"]
