"use client";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { Conversation } from "@/lib/api";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete }: SidebarProps) {
  return (
    <aside
      className="w-64 h-full flex flex-col border-r"
      style={{ background: "#1a1d27", borderColor: "#2e3354" }}
    >
      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: "#2e3354" }}>
        <span className="font-bold text-sm tracking-wide" style={{ color: "#7b93ff" }}>
          💬 HITL Chatbot
        </span>
        <button
          onClick={onNew}
          className="p-1.5 rounded-lg hover:bg-white/10 transition"
          title="New conversation"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.length === 0 && (
          <p className="text-xs text-center mt-8" style={{ color: "#8890b0" }}>
            No conversations yet
          </p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className="group flex items-start gap-2 rounded-lg px-3 py-2 cursor-pointer text-sm transition"
            style={{
              background: activeId === conv.id ? "#22263a" : "transparent",
              color: activeId === conv.id ? "#e8eaf6" : "#8890b0",
            }}
          >
            <MessageSquare size={14} className="mt-0.5 flex-shrink-0" />
            <span className="flex-1 truncate text-xs leading-5">{conv.preview || "New conversation"}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}
              className="opacity-0 group-hover:opacity-100 transition p-0.5 rounded hover:text-red-400"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="p-3 border-t text-xs" style={{ borderColor: "#2e3354", color: "#8890b0" }}>
        LangGraph + FastAPI + Next.js
      </div>
    </aside>
  );
}
