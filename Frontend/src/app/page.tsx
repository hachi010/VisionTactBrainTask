"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Loader2, Bot } from "lucide-react";
import ChatBubble, { type ChatMessage } from "@/components/ChatBubble";
import Sidebar from "@/components/Sidebar";
import { chatApi, type Conversation } from "@/lib/api";

let msgCounter = 0;
const uid = () => `msg-${++msgCounter}`;

export default function Home() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Load conversation list
  const loadConversations = useCallback(async () => {
    try {
      const convs = await chatApi.getConversations();
      setConversations(convs);
    } catch {/* ignore */}
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load messages when switching conversations
  const selectConversation = useCallback(async (id: string) => {
    setActiveConvId(id);
    try {
      const msgs = await chatApi.getMessages(id);
      setMessages(
        msgs
          .filter((m) => m.role !== "tool")
          .map((m) => ({
            id: uid(),
            role: m.role as "user" | "assistant",
            content: m.content,
          }))
      );
    } catch {/* ignore */}
  }, []);

  const newConversation = () => {
    setActiveConvId(null);
    setMessages([]);
  };

  const deleteConversation = async (id: string) => {
    await chatApi.deleteConversation(id);
    if (activeConvId === id) newConversation();
    loadConversations();
  };

  // Poll for background task result
  const startPolling = (taskId: string, approvalMsgId: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const status = await chatApi.pollTaskStatus(taskId);
        if (status.status === "completed") {
          clearInterval(pollingRef.current!);
          setMessages((prev) => [
            ...prev,
            { id: uid(), role: "assistant", content: status.reply || "Done." },
          ]);
          loadConversations();
        } else if (status.status === "failed") {
          clearInterval(pollingRef.current!);
          setMessages((prev) => [
            ...prev,
            { id: uid(), role: "assistant", content: `❌ Task failed: ${status.error}` },
          ]);
        }
      } catch {
        clearInterval(pollingRef.current!);
      }
    }, 1500);
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    // Typing indicator
    const typingId = uid();
    setMessages((prev) => [
      ...prev,
      { id: typingId, role: "assistant", content: "…" },
    ]);

    try {
      const res = await chatApi.sendMessage(text, activeConvId || undefined);

      // Update active conversation id
      if (!activeConvId) setActiveConvId(res.conversation_id);

      // Remove typing indicator
      setMessages((prev) => prev.filter((m) => m.id !== typingId));

      if (res.requires_approval && res.task_id) {
        const approvalMsgId = uid();
        setMessages((prev) => [
          ...prev,
          {
            id: approvalMsgId,
            role: "approval",
            content: "This action requires your approval before proceeding:",
            taskId: res.task_id,
            toolName: res.pending_tool,
            toolArgs: res.pending_tool_args || {},
            approved: null,
          },
        ]);
      } else if (res.reply) {
        setMessages((prev) => [
          ...prev,
          { id: uid(), role: "assistant", content: res.reply! },
        ]);
      }

      loadConversations();
    } catch (err: unknown) {
      setMessages((prev) => prev.filter((m) => m.id !== typingId));
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: "⚠️ Something went wrong. Please check that the backend is running.",
        },
      ]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleApprove = async (taskId: string) => {
    setApprovalLoading(true);
    // Mark approval card as approved
    setMessages((prev) =>
      prev.map((m) => (m.taskId === taskId ? { ...m, approved: true } : m))
    );
    try {
      await chatApi.approveTask(taskId);
      // Add "running" message and start polling
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", content: "⚙️ Running task in background…" },
      ]);
      startPolling(taskId, taskId);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", content: "❌ Failed to approve task." },
      ]);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleReject = async (taskId: string) => {
    setApprovalLoading(true);
    setMessages((prev) =>
      prev.map((m) => (m.taskId === taskId ? { ...m, approved: false } : m))
    );
    try {
      const res = await chatApi.rejectTask(taskId);
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", content: res.reply },
      ]);
      loadConversations();
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", content: "❌ Failed to reject task." },
      ]);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={deleteConversation}
      />

      {/* Main chat area */}
      <main className="flex flex-col flex-1 overflow-hidden">
        {/* Topbar */}
        <div
          className="h-12 flex items-center px-4 border-b flex-shrink-0"
          style={{ background: "#1a1d27", borderColor: "#2e3354" }}
        >
          <Bot size={18} style={{ color: "#4361ee" }} className="mr-2" />
          <span className="text-sm font-semibold" style={{ color: "#e8eaf6" }}>
            Memory-Enabled HITL Chatbot
          </span>
          <span
            className="ml-3 text-xs px-2 py-0.5 rounded-full"
            style={{ background: "#22c55e22", color: "#22c55e", border: "1px solid #22c55e44" }}
          >
            LangGraph
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4" style={{ background: "#0f1117" }}>
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                   style={{ background: "#22263a" }}>
                <Bot size={28} style={{ color: "#4361ee" }} />
              </div>
              <h2 className="text-lg font-semibold" style={{ color: "#e8eaf6" }}>
                How can I help you today?
              </h2>
              <p className="text-sm max-w-xs" style={{ color: "#8890b0" }}>
                Ask me anything. For GitHub or LinkedIn actions, I'll ask for your approval first.
              </p>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {[
                  "Crawl this repo: https://github.com/openai/openai-python",
                  "Search GitHub for LangGraph examples",
                  "What is Human-in-the-Loop AI?",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="text-xs px-3 py-1.5 rounded-lg border transition hover:border-blue-500/50"
                    style={{ background: "#1a1d27", border: "1px solid #2e3354", color: "#8890b0" }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              onApprove={handleApprove}
              onReject={handleReject}
              approvalLoading={approvalLoading}
            />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div
          className="border-t px-4 py-3 flex-shrink-0"
          style={{ background: "#1a1d27", borderColor: "#2e3354" }}
        >
          <div
            className="flex items-end gap-2 rounded-xl border px-3 py-2"
            style={{ background: "#0f1117", borderColor: "#2e3354" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message… (Enter to send, Shift+Enter for newline)"
              rows={1}
              className="flex-1 bg-transparent resize-none text-sm outline-none placeholder-gray-600"
              style={{ maxHeight: "160px", color: "#e8eaf6" }}
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="p-2 rounded-lg transition disabled:opacity-40"
              style={{ background: "#4361ee" }}
            >
              {sending ? <Loader2 size={16} className="animate-spin text-white" /> : <Send size={16} className="text-white" />}
            </button>
          </div>
          <p className="text-xs mt-1.5 text-center" style={{ color: "#8890b0" }}>
            GitHub & LinkedIn actions require approval · Powered by LangGraph
          </p>
        </div>
      </main>
    </div>
  );
}
