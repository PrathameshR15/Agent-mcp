from typing import Dict, Any, List
from app.models.domain import JobRequest
import uuid
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load the model once globally so it is blazing fast on subsequent requests
print("Loading all-MiniLM-L6-v2 model for auto-routing...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

# Define capabilities and their descriptions for semantic matching
CAPABILITY_DESCRIPTIONS = {
    "manage_traffic": "handles all issues related to roads, vehicles, traffic control, public transit, and commuting",
    "waste_collection": "handles garbage, recycling, street cleaning, sanitation, and waste disposal",
    "infrastructure_repair": "handles physical infrastructure repair, public works, road maintenance, and civil engineering",
    "noise_complaints": "handles law enforcement, public safety, parking enforcement, and community policing",
    "fire_hazards": "handles emergency rescue, fire prevention, hazardous materials, and urgent safety threats",
    "park_maintenance": "handles landscaping, public parks, recreation facilities, trees, and green spaces",
    "water_leaks": "handles plumbing, water supply, sewage, drainage, and liquid utility infrastructure",
    "process_alert": "handles security cameras, video surveillance, camera alerts, intrusion detection, and monitoring"
}

CAP_KEYS = list(CAPABILITY_DESCRIPTIONS.keys())
CAP_TEXTS = list(CAPABILITY_DESCRIPTIONS.values())
# Precompute embeddings for capabilities
CAP_EMBEDDINGS = embedding_model.encode(CAP_TEXTS)

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
        # Extract all text values from the JSON payload
        if isinstance(payload, dict):
            # Exclude base64 strings if any exist
            content_str = " ".join([str(v) for k, v in payload.items() if isinstance(v, str) and not k.endswith("base64")])
        else:
            content_str = str(payload)
            
        if not content_str.strip():
            return []
            
        # Get embedding of the user's complaint
        query_embedding = embedding_model.encode([content_str.lower()])
        
        # Calculate cosine similarity with all capability descriptions
        similarities = cosine_similarity(query_embedding, CAP_EMBEDDINGS)[0]
        
        # Create a list of tuples: (score, cap_key)
        scored_caps = [(score, CAP_KEYS[idx]) for idx, score in enumerate(similarities)]
        
        # Sort by score descending (highest first)
        scored_caps.sort(reverse=True, key=lambda x: x[0])
        
        matched_caps = []
        # Only iterate over the top 2 highest scoring capabilities
        for score, cap_key in scored_caps[:2]:
            # Still enforce a minimum threshold just in case
            if score > 0.15:
                print(f"Auto-routing match: {cap_key} (Score: {score:.2f})")
                matched_caps.append(cap_key)
                
        return matched_caps

ingestor = DataIngestor()
