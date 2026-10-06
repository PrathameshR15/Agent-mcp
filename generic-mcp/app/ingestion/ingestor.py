from typing import Dict, Any, List
from app.models.domain import JobRequest
import uuid

class DataIngestor:
    def process_input(self, data_type: str, payload: Dict[str, Any], requirements: List[str]) -> JobRequest:
        # Auto-detect requirements if none are provided
        if not requirements:
            requirements = self._auto_detect_requirements(data_type, payload)
            
        request = JobRequest(
            data_id=str(uuid.uuid4()),
            data_type=data_type,
            payload=payload,
            requirements=requirements
        )
        return request

    def _auto_detect_requirements(self, data_type: str, payload: Dict[str, Any]) -> List[str]:
        reqs = []
        content_str = str(payload).lower()
        
        # Check by keywords in the payload
        if "temp" in content_str or "celsius" in content_str or "weather" in content_str:
            reqs.append("analyze_temperature")
        if "pothole" in content_str or "road" in content_str or "highway" in content_str:
            reqs.append("detect_pothole")
        if "speed" in content_str or "limit" in content_str or "highway" in content_str:
            reqs.append("detect_speed_limit")
        if "radar" in content_str or "scan" in content_str:
            reqs.append("process_radar")
        if "log" in content_str or "event" in content_str or "timestamp" in content_str:
            reqs.append("parse_logs")
            
        # Fallbacks by data_type if we still don't know
        if not reqs:
            if "image" in data_type:
                reqs.extend(["detect_pothole", "detect_speed_limit"])
            elif "csv" in data_type:
                reqs.append("parse_logs")
            elif "json" in data_type:
                # Default generic json to parse_logs or analyze_temperature?
                # Let's say parse_logs as a generic fallback for JSON data events
                reqs.append("parse_logs")
                
        return list(set(reqs))

ingestor = DataIngestor()
