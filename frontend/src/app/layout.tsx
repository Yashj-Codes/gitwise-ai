import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GitWise — AI-Powered GitHub Repository Intelligence",
  description:
    "Paste any GitHub repo URL and instantly chat with the codebase using AI. Powered by LangChain, LangGraph, and Google Gemini.",
  keywords: ["github", "AI", "code analysis", "LangChain", "LangGraph", "RAG", "chatbot"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
