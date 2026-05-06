import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, Message, PendingTask, init_db, get_db
from memory import get_or_create_conversation, load_messages, save_message, list_conversations
from agent import graph, AgentState, run_approved_graph, run_rejected_graph

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


# ─── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="HITL Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pending_approvals: dict[str, dict] = {}


# ─── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str | None = None
    requires_approval: bool = False
    task_id: str | None = None
    pending_tool: str | None = None
    pending_tool_args: dict | None = None


class ApprovalResponse(BaseModel):
    conversation_id: str
    reply: str


# ─── Background task runner ────────────────────────────────────────────────────

async def _run_approved_task(task_id: str, conversation_id: str, state: AgentState):
    async with AsyncSessionLocal() as session:
        try:
            new_state = await run_approved_graph(state)

            reply = ""
            for msg in reversed(new_state["messages"]):
                if isinstance(msg, AIMessage) and msg.content:
                    reply = msg.content
                    break

            await save_message(session, conversation_id, "assistant", reply)

            await session.execute(
                update(PendingTask)
                .where(PendingTask.id == task_id)
                .values(status="completed", result=reply)
            )
            await session.commit()

            _pending_approvals[task_id]["result"] = reply
            _pending_approvals[task_id]["done"] = True

        except Exception as e:
            await session.execute(
                update(PendingTask)
                .where(PendingTask.id == task_id)
                .values(status="failed", result=str(e))
            )
            await session.commit()
            _pending_approvals[task_id]["error"] = str(e)
            _pending_approvals[task_id]["done"] = True


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    conversation_id = await get_or_create_conversation(db, req.conversation_id)

    history = await load_messages(db, conversation_id)
    history.append(HumanMessage(content=req.message))
    await save_message(db, conversation_id, "user", req.message)

    initial_state: AgentState = {
        "messages": history,
        "pending_tool_calls": [],
        "approval_status": None,
        "task_id": None,
    }

    result_state = await graph.ainvoke(initial_state, config={"recursion_limit": 20})

    # Stopped at request_approval — needs human decision
    if result_state.get("approval_status") == "pending":
        task_id = result_state["task_id"] or str(uuid.uuid4())
        pending_calls = result_state.get("pending_tool_calls", [])
        first_tool = pending_calls[0] if pending_calls else {}

        db.add(PendingTask(
            id=task_id,
            conversation_id=conversation_id,
            tool_name=first_tool.get("name", ""),
            tool_args=first_tool.get("args", {}),
            status="pending",
        ))
        await db.commit()

        _pending_approvals[task_id] = {
            "state": result_state,
            "conversation_id": conversation_id,
            "done": False,
        }

        return ChatResponse(
            conversation_id=conversation_id,
            requires_approval=True,
            task_id=task_id,
            pending_tool=first_tool.get("name", ""),
            pending_tool_args=first_tool.get("args", {}),
        )

    # Normal reply
    reply = ""
    for msg in reversed(result_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    await save_message(db, conversation_id, "assistant", reply)

    return ChatResponse(
        conversation_id=conversation_id,
        reply=reply,
        requires_approval=False,
    )


@app.post("/api/tasks/{task_id}/approve", response_model=ApprovalResponse)
async def approve_task(task_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    pending = _pending_approvals.get(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Task not found or already processed")

    conversation_id = pending["conversation_id"]
    state = pending["state"]

    await db.execute(update(PendingTask).where(PendingTask.id == task_id).values(status="approved"))
    await db.commit()

    background_tasks.add_task(_run_approved_task, task_id, conversation_id, state)

    return ApprovalResponse(conversation_id=conversation_id, reply="Task approved. Running in background…")


@app.post("/api/tasks/{task_id}/reject", response_model=ApprovalResponse)
async def reject_task(task_id: str, db: AsyncSession = Depends(get_db)):
    pending = _pending_approvals.pop(task_id, None)
    if not pending:
        raise HTTPException(status_code=404, detail="Task not found or already processed")

    conversation_id = pending["conversation_id"]
    state = pending["state"]

    await db.execute(update(PendingTask).where(PendingTask.id == task_id).values(status="rejected"))
    await db.commit()

    new_state = await run_rejected_graph(state)

    reply = ""
    for msg in reversed(new_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    await save_message(db, conversation_id, "assistant", reply)

    return ApprovalResponse(conversation_id=conversation_id, reply=reply)


@app.get("/api/tasks/{task_id}/status")
async def task_status(task_id: str):
    pending = _pending_approvals.get(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Task not found")

    if pending.get("done"):
        result = pending.get("result", "")
        error = pending.get("error")
        _pending_approvals.pop(task_id, None)
        if error:
            return {"status": "failed", "error": error}
        return {"status": "completed", "reply": result}

    return {"status": "running"}


@app.get("/api/conversations")
async def get_conversations(db: AsyncSession = Depends(get_db)):
    return await list_conversations(db)


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "tool_name": r.tool_name,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(PendingTask).where(PendingTask.conversation_id == conversation_id))
    from database import Conversation
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()
    return {"status": "deleted"}


@app.get("/health")
async def health():
    return {"status": "ok"}