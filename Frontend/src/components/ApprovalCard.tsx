"use client";
import { CheckCircle, XCircle, Github, Linkedin, Loader2 } from "lucide-react";

interface ApprovalCardProps {
  toolName: string;
  toolArgs: Record<string, unknown>;
  onApprove: () => void;
  onReject: () => void;
  loading?: boolean;
}

const TOOL_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  crawl_github_repo:      { icon: <Github size={18} />, label: "Crawl GitHub Repo",        color: "#4361ee" },
  search_github_repos:    { icon: <Github size={18} />, label: "Search GitHub Repos",      color: "#4361ee" },
  crawl_linkedin_profile: { icon: <Linkedin size={18} />, label: "Crawl LinkedIn Profile", color: "#0a66c2" },
  search_linkedin_profiles:{ icon: <Linkedin size={18} />, label: "Search LinkedIn",       color: "#0a66c2" },
};

export default function ApprovalCard({ toolName, toolArgs, onApprove, onReject, loading }: ApprovalCardProps) {
  const meta = TOOL_META[toolName] || { icon: null, label: toolName, color: "#4361ee" };

  return (
    <div
      className="rounded-xl border p-4 my-2 max-w-md"
      style={{ background: "#1a1d27", borderColor: meta.color + "66" }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span style={{ color: meta.color }}>{meta.icon}</span>
        <span className="font-semibold text-sm" style={{ color: meta.color }}>
          Tool Approval Required
        </span>
      </div>

      <p className="text-sm text-gray-300 mb-1">
        The assistant wants to run: <strong className="text-white">{meta.label}</strong>
      </p>

      {/* Args */}
      <div className="rounded-lg p-3 text-xs font-mono mt-2 mb-4 overflow-auto max-h-36"
           style={{ background: "#0f1117", border: "1px solid #2e3354", color: "#a5b4fc" }}>
        {Object.entries(toolArgs).map(([k, v]) => (
          <div key={k}>
            <span className="text-gray-500">{k}:</span>{" "}
            <span>{String(v)}</span>
          </div>
        ))}
      </div>

      {/* Buttons */}
      <div className="flex gap-2">
        <button
          onClick={onApprove}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
          style={{ background: "#22c55e" }}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
          Approve
        </button>
        <button
          onClick={onReject}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
          style={{ background: "#ef4444" }}
        >
          <XCircle size={14} />
          Reject
        </button>
      </div>
    </div>
  );
}
