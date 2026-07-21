# Manager Agent Standalone Project

A self-contained, minimal version of the Manager Agent from the EDAS project.

## Quick Start

```bash
# Start all services (PostgreSQL, backend, frontend)
docker-compose up -d

# Access the frontend
http://localhost:7008

# Access the backend API
http://localhost:7009
```

## Project Structure

```
components-build/manager-agent/
├── docker-compose.yml
├── backend/
│  ├── Dockerfile
│  ├── requirements.txt
│  ├── .env.example
│  ├── config.py
│  ├── api/
│  │  ├── server.py
│  │  ├── auth.py
│  │  ├── websocket.py
│  │  └── routes/manager.py
│  ├── bus/
│  ├── agents/
│  │  ├── manager/
│  │  ├── planner_agent.py
│  │  └── executor_agent.py
│  ├── db/
│  ├── scheduler/
│  └── llm/
└── frontend/
   ├── Dockerfile
   ├── package.json
   ├── vite.config.ts
   └── src/
       ├── api/manager.ts
       ├── hooks/useWebSocket.ts
       ├── stores/
       ├── types/manager.ts
       ├── pages/WorkspacePage.tsx
       └── sections/
           ├── ChatSection.tsx
           ├── OutputSection.tsx
           └── ContextSection.tsx
```

## Features

- **LangGraph-based Manager Agent**: Conversational AI for IoT data analysis
- **Planner Agent**: Plans and executes data queries (renamed from Research Agent)
- **Executor Agent**: Runs pandas queries against data
- **PostgreSQL Message Bus**: Event-driven architecture
- **Real-time WebSocket**: Live streaming of results to frontend
- **React Dashboard**: Conversational workspace with chat, output, and context sections

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --port 7009
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `POST /manager/sessions` - Create new session
- `GET /manager/sessions` - List all sessions
- `GET /manager/sessions/{id}` - Get session details
- `POST /manager/sessions/{id}/messages` - Send message to manager agent
- `WS /ws` - WebSocket for real-time updates

## Database

Uses PostgreSQL with the following tables:
- `events` - Message bus queue
- `results` - Analysis results
- `chat_history` - Chat turns per session
- `manager_sessions` - Active session state
- `global_registry` - IoT line catalog
- `task_registry` - Saved task definitions
- `users` - User accounts

## LLM Integration

Connects to vLLM serving on DGX Spark at `http://dgx-spark:8009/v1`
Model: `atlas-35b` (Qwen3.5-35B-A3B-NVFP4)

## Notes

This is a standalone, minimal version extracted from the full EDAS project.
All critical bugs have been fixed in this copy.