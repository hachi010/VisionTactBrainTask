"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot } from "lucide-react";
import ApprovalCard from "./ApprovalCard";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "approval";
  content: string;
  taskId?: string;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  approved?: boolean | null; // null = pending, true = approved, false = rejected
}

interface Props {
  message: ChatMessage;
  onApprove?: (taskId: string) => void;
  onReject?: (taskId: string) => void;
  approvalLoading?: boolean;
}

export default function ChatBubble({ message, onApprove, onReject, approvalLoading }: Props) {
  const isUser = message.role === "user";
  const isApproval = message.role === "approval";

  if (isApproval && message.taskId) {
    const resolved = message.approved !== null && message.approved !== undefined;
    return (
      <div className="flex gap-3 items-start py-2">
        <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
             style={{ background: "#22263a" }}>
          <Bot size={16} style={{ color: "#4361ee" }} />
        </div>
        <div>
          <p className="text-sm mb-1" style={{ color: "#8890b0" }}>
            {message.content}
          </p>
          {!resolved ? (
            <ApprovalCard
              toolName={message.toolName!}
              toolArgs={message.toolArgs!}
              onApprove={() => onApprove?.(message.taskId!)}
              onReject={() => onReject?.(message.taskId!)}
              loading={approvalLoading}
            />
          ) : (
            <div className="text-xs py-1 px-3 rounded-full inline-block"
                 style={{
                   background: message.approved ? "#15803d22" : "#ef444422",
                   color: message.approved ? "#22c55e" : "#ef4444",
                   border: `1px solid ${message.approved ? "#22c55e44" : "#ef444444"}`,
                 }}>
              {message.approved ? "✓ Approved — running in background…" : "✗ Rejected"}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 items-start py-2 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ background: isUser ? "#4361ee22" : "#22263a" }}
      >
        {isUser
          ? <User size={16} style={{ color: "#4361ee" }} />
          : <Bot size={16} style={{ color: "#7b93ff" }} />
        }
      </div>

      {/* Bubble */}
      <div
        className={`rounded-2xl px-4 py-2.5 max-w-[75%] text-sm leading-relaxed ${isUser ? "rounded-tr-sm" : "rounded-tl-sm"}`}
        style={{
          background: isUser ? "#4361ee" : "#1a1d27",
          color: isUser ? "#fff" : "#e8eaf6",
          border: isUser ? "none" : "1px solid #2e3354",
        }}
      >
        {isUser ? (
          <p style={{ margin: 0 }}>{message.content}</p>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
