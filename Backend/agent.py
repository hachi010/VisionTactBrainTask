from __future__ import annotations

import os
import uuid
from typing import Annotated, Any, Literal, TypedDict

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from tools import ALL_TOOLS, TOOLS_BY_NAME, TOOLS_REQUIRING_APPROVAL

# ─── LLM ───────────────────────────────────────────────────────────────────────

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
).bind_tools(ALL_TOOLS)

SYSTEM_PROMPT = """You are a helpful AI assistant with the ability to interact with GitHub and LinkedIn.

When a user asks you to perform a GitHub action (like crawling a repo or searching repos) or a
LinkedIn action (like crawling a profile or searching profiles), you MUST use the appropriate tool.

For all other questions, answer conversationally.

Be concise and helpful. When tool results come back, summarise them clearly for the user."""


# ─── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pending_tool_calls: list[dict]
    approval_status: str | None   # None | "pending" | "approved" | "rejected"
    task_id: str | None


# ─── Nodes ─────────────────────────────────────────────────────────────────────

def chat_node(state: AgentState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {
        "messages": [response],
        "pending_tool_calls": [],
        "approval_status": None,
        "task_id": None,
    }


def request_approval_node(state: AgentState) -> dict:
    """
    Signal that approval is needed. Sets status to 'pending' and stops.
    The API layer detects this and returns a 202 with task info to the frontend.
    The graph does NOT continue from here — the API resumes it separately
    via run_approved_graph() or run_rejected_graph().
    """
    last_ai = state["messages"][-1]
    approval_tools = [tc for tc in last_ai.tool_calls if tc["name"] in TOOLS_REQUIRING_APPROVAL]
    task_id = str(uuid.uuid4())
    return {
        "pending_tool_calls": approval_tools,
        "task_id": task_id,
        "approval_status": "pending",
    }


async def run_tools_node(state: AgentState) -> dict:
    last_ai = state["messages"][-1]
    tool_messages: list[BaseMessage] = []

    for tc in last_ai.tool_calls:
        tool_fn = TOOLS_BY_NAME.get(tc["name"])
        if tool_fn is None:
            result = f"Unknown tool: {tc['name']}"
        else:
            try:
                result = await tool_fn.ainvoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {str(e)}"

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"], name=tc["name"])
        )

    return {"messages": tool_messages}


def rejected_node(state: AgentState) -> dict:
    last_ai = state["messages"][-1]
    tool_names = ", ".join(
        tc["name"] for tc in last_ai.tool_calls if tc["name"] in TOOLS_REQUIRING_APPROVAL
    )
    msg = AIMessage(
        content=f"Understood — I won't run {tool_names}. Is there anything else I can help you with?"
    )
    return {
        "messages": [msg],
        "pending_tool_calls": [],
        "approval_status": None,
        "task_id": None,
    }


# ─── Two separate mini-graphs for post-approval ────────────────────────────────

def build_approved_graph():
    """Graph that runs tools then chats — used after user approves."""
    g = StateGraph(AgentState)
    g.add_node("run_tools", run_tools_node)
    g.add_node("chat", chat_node)
    g.set_entry_point("run_tools")
    g.add_edge("run_tools", "chat")
    g.add_edge("chat", END)
    return g.compile()


def build_rejected_graph():
    """Graph that just sends the rejection message."""
    g = StateGraph(AgentState)
    g.add_node("rejected", rejected_node)
    g.set_entry_point("rejected")
    g.add_edge("rejected", END)
    return g.compile()


# ─── Main graph (stops at request_approval) ────────────────────────────────────

def build_main_graph():
    g = StateGraph(AgentState)

    g.add_node("chat", chat_node)
    g.add_node("request_approval", request_approval_node)
    g.add_node("run_tools", run_tools_node)

    g.set_entry_point("chat")

    def router(state: AgentState):
        last = state["messages"][-1]
        if not (isinstance(last, AIMessage) and last.tool_calls):
            return "end"
        for tc in last.tool_calls:
            if tc["name"] in TOOLS_REQUIRING_APPROVAL:
                return "request_approval"
        return "run_tools"

    g.add_conditional_edges(
        "chat",
        router,
        {"request_approval": "request_approval", "run_tools": "run_tools", "end": END},
    )
    g.add_edge("request_approval", END)
    g.add_edge("run_tools", "chat")

    return g.compile()


graph = build_main_graph()
approved_graph = build_approved_graph()
rejected_graph = build_rejected_graph()


# ─── Resume helpers called by FastAPI ─────────────────────────────────────────

async def run_approved_graph(state: AgentState) -> AgentState:
    return await approved_graph.ainvoke(state, config={"recursion_limit": 20})


async def run_rejected_graph(state: AgentState) -> AgentState:
    return await rejected_graph.ainvoke(state, config={"recursion_limit": 20})