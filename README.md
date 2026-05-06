🤖 Memory-Enabled HITL Chatbot
A full-stack chatbot using LangChain + LangGraph with Human-in-the-Loop (HITL) tool approvals, persistent conversation memory, and a clean Next.js chat UI.

🏗 Architecture
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                        │
│  Chat UI  │  Sidebar (history)  │  Approve/Reject Cards      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (REST)
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend                            │
│  POST /api/chat   POST /api/tasks/{id}/approve|reject        │
│  GET  /api/conversations   GET /api/tasks/{id}/status        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  LangGraph Agent                              │
│                                                              │
│  [chat] → [check_tools] → needs approval?                    │
│                               YES → [request_approval] ──►  │
│                                     User: Approve / Reject   │
│                                         │         │          │
│                               [run_tools]    [rejected]      │
│                                    │                         │
│                                 [chat]                       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              SQLite (via SQLAlchemy async)                    │
│  conversations  │  messages  │  pending_tasks                │
└─────────────────────────────────────────────────────────────┘

🚀 Quick Start
Prerequisites

Python 3.11+
Node.js 20+
OpenAI API key
Github Token

1. Clone & configure
bashgit clone <your-repo>
cd <repo>
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and GITHUB TOKEN

2. Backend
bashcd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # add your keys
uvicorn main:app --reload
Backend runs at http://localhost:8000
API docs at http://localhost:8000/docs

3. Frontend
bashcd frontend
npm install
npm run dev
Frontend runs at http://localhost:3000
