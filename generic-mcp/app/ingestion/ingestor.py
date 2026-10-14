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
    def process_input(self, data_type: str, payload: Any, requirements: List[str]) -> JobRequest:
        # Normalize payload to dictionary if it is a list or primitive
        if isinstance(payload, list):
            payload = {"items": payload}
        elif not isinstance(payload, dict):
            payload = {"content": str(payload)}

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

    def _auto_detect_requirements(self, data_type: str, payload: Any) -> List[str]:
        # Recursively extract all text keys and values from the JSON payload
        def _extract_text(obj):
            if isinstance(obj, dict):
                parts = []
                for k, v in obj.items():
                    if not str(k).endswith("base64") and not str(v).endswith("base64"):
                        parts.append(f"{k}: {_extract_text(v)}")
                return " ".join(parts)
            elif isinstance(obj, list):
                return " ".join([_extract_text(item) for item in obj])
            return str(obj)

        content_str = _extract_text(payload)
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
        # Select the single best matching capability
        for score, cap_key in scored_caps[:1]:
            # Still enforce a minimum threshold just in case
            if score > 0.15:
                print(f"Auto-routing match: {cap_key} (Score: {score:.2f})")
                matched_caps.append(cap_key)
                
        return matched_caps

    def register_capability(self, cap_name: str, description: str):
        global CAP_KEYS, CAP_TEXTS, CAP_EMBEDDINGS
        if cap_name not in CAPABILITY_DESCRIPTIONS:
            CAPABILITY_DESCRIPTIONS[cap_name] = description
            CAP_KEYS = list(CAPABILITY_DESCRIPTIONS.keys())
            CAP_TEXTS = list(CAPABILITY_DESCRIPTIONS.values())
            CAP_EMBEDDINGS = embedding_model.encode(CAP_TEXTS)
            print(f"[Ingestor] Dynamically registered capability '{cap_name}': {description}")

ingestor = DataIngestor()
