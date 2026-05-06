import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HITL Chatbot",
  description: "Memory-enabled chatbot with Human-in-the-Loop tool approvals",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
