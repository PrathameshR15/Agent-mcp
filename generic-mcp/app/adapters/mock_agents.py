import asyncio
from typing import Dict, Any, List
from app.adapters.base import BaseAgentAdapter

class MockPotholeAgentAdapter(BaseAgentAdapter):
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(1) # Simulate processing
        return {
            "status": "success",
            "findings": [
                {"type": "pothole", "confidence": 0.95, "location": "x:10, y:20"}
            ]
        }

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        return ["detect_pothole"]


class MockSpeedLimitAgentAdapter(BaseAgentAdapter):
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(1) # Simulate processing
        return {
            "status": "success",
            "findings": [
                {"type": "speed_limit_sign", "value": 60, "confidence": 0.98}
            ]
        }

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        return ["detect_speed_limit"]

class MockTempAnomalyAgentAdapter(BaseAgentAdapter):
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.5)
        temp = data.get("temperature", 0)
        return {
            "status": "success",
            "alert": temp > 40,
            "message": "Temperature exceeds safe threshold!" if temp > 40 else "Temperature normal."
        }

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        return ["analyze_temperature"]

class MockRadarAgentAdapter(BaseAgentAdapter):
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(1.5)
        return {
            "status": "success",
            "findings": [
                {"object": "vehicle", "speed": 85, "distance": 120}
            ]
        }

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        return ["process_radar"]

class MockLogAnalyzerAgentAdapter(BaseAgentAdapter):
    async def process(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.8)
        return {
            "status": "success",
            "anomalies_found": 0,
            "parsed_lines": 2
        }

    async def health_check(self) -> bool:
        return True

    def get_capabilities(self) -> List[str]:
        return ["parse_logs"]
