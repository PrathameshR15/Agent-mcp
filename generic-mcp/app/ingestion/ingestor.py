from typing import Dict, Any, List
from app.models.domain import JobRequest
import uuid

class DataIngestor:
    def process_input(self, data_type: str, payload: Dict[str, Any], requirements: List[str]) -> JobRequest:
        # Here we would normally store large files externally and replace with references
        # For MVP, we pass the payload as is
        
        request = JobRequest(
            data_id=str(uuid.uuid4()),
            data_type=data_type,
            payload=payload,
            requirements=requirements
        )
        return request

ingestor = DataIngestor()
