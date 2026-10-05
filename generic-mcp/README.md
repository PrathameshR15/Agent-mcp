# Generic Multi-Agent MCP Platform

A production-ready Multi-Agent MCP (Model Context Protocol) Platform.

## Architecture

*   **MCP Server (`app/main.py`)**: Handles MCP protocol communication via SSE and standard REST endpoints.
*   **Ingestion (`app/ingestion/ingestor.py`)**: Accepts and validates incoming data.
*   **Registry (`app/registry/agent_registry.py`)**: Manages available agents, their capabilities, and statuses.
*   **Routing (`app/routing/router.py`)**: Matches job requirements to available agents based on capabilities and input types.
*   **Dispatcher (`app/dispatcher/dispatcher.py`)**: Executes jobs across matched agents using their respective adapters.
*   **Adapters (`app/adapters/`)**: Interface implementations for specific agents. MVP includes Mock Pothole and Speed Limit agents.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
uvicorn app.main:app --reload
```

## Usage

**Submit a Job via REST:**
```bash
curl -X POST http://localhost:8000/api/submit -H "Content-Type: application/json" -d '{"data_type": "image/jpeg", "payload": {"url": "http://example.com/image.jpg"}, "requirements": ["detect_pothole"]}'
```

**Check Job Status:**
```bash
curl http://localhost:8000/api/jobs/<job_id>
```

**List Agents:**
```bash
curl http://localhost:8000/api/agents
```

**MCP Endpoints:**
* SSE connection: `GET /sse`
* Post messages: `POST /messages/`
