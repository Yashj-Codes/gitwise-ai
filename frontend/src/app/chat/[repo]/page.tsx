"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  isStreaming?: boolean;
}

const SUGGESTIONS = [
  "What does this repository do?",
  "Explain the main architecture",
  "What are the key dependencies?",
  "How does authentication work?",
  "Show me the entry point of the app",
];

function MarkdownContent({ text }: { text: string }) {
  // Simple markdown renderer — handles code blocks, inline code, bold, links
  const renderMarkdown = (content: string) => {
    // Process code blocks first to protect them from other replacements
    const codeBlocks: string[] = [];
    let processed = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code class="language-${lang || ''}">${escapeHtml(code.trim())}</code></pre>`);
      return `__CODEBLOCK_${idx}__`;
    });

    processed = processed
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>[^<]*<\/li>[\n\r]*)+/g, (m) => `<ul>${m}</ul>`)
      .replace(/\n\n/g, "</p><p>")
      .replace(/^([^<\n].+)$/gm, (m) =>
        m.startsWith("<") ? m : `<p>${m}</p>`
      );

    // Restore code blocks
    return processed.replace(/__CODEBLOCK_(\d+)__/g, (_, i) => codeBlocks[Number(i)]);
  };

  const escapeHtml = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  return (
    <div
      className="markdown-content"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
    />
  );
}

export default function ChatPage() {
  const params = useParams();
  const repoUrl = decodeURIComponent(params.repo as string);
  const repoName = repoUrl.replace("https://github.com/", "");

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [repoStats, setRepoStats] = useState<{ indexed: boolean }>({ indexed: false });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Check repo status on load
  useEffect(() => {
    const repoId = repoUrl
      .replace("https://github.com/", "")
      .replace(/\//g, "_")
      .replace(/[^\w\-]/g, "_");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
    fetch(`${apiUrl}/api/status/${repoId}`)
      .then((r) => r.json())
      .then((d) => setRepoStats(d))
      .catch(() => {});
  }, [repoUrl]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "52px";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  async function sendMessage(question: string) {
    if (!question.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsLoading(true);

    const allMessages = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user" as const, content: question },
    ];

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, messages: allMessages }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";
      let finalSources: string[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split("\n").filter((l) => l.startsWith("data:"));

        for (const line of lines) {
          const json = line.replace("data: ", "").trim();
          if (!json) continue;
          const event = JSON.parse(json);

          if (event.type === "token") {
            accumulated += event.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: accumulated, isStreaming: true }
                  : m
              )
            );
          } else if (event.type === "done") {
            finalSources = event.sources || [];
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, isStreaming: false, sources: finalSources }
                  : m
              )
            );
          } else if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                content: `❌ Error: ${msg}`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="page-wrapper" style={{ padding: 0 }}>
      <div className="bg-animated" />

      <div className="chat-layout">
        {/* Sidebar */}
        <aside className="chat-sidebar">
          <div className="sidebar-header">
            <div className="sidebar-repo-name">📦 {repoName}</div>
            <div className="sidebar-repo-url">{repoUrl}</div>
          </div>

          <div className="sidebar-stats">
            <div className="stat-item">
              <span className="stat-label">Status</span>
              <span
                className="stat-value"
                style={{ color: repoStats.indexed ? "var(--accent-green)" : "var(--accent-red)" }}
              >
                {repoStats.indexed ? "✅ Indexed" : "⏳ Indexing"}
              </span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Messages</span>
              <span className="stat-value">{messages.length}</span>
            </div>
          </div>

          <div className="sidebar-tech-stack">
            <div className="sidebar-tech-title">Powered By</div>
            <div className="tech-badges">
              <span className="badge badge-langchain tech-badge">LangChain</span>
              <span className="badge badge-langgraph tech-badge">LangGraph</span>
              <span className="badge badge-gemini tech-badge">Gemini 1.5</span>
              <span
                className="tech-badge badge"
                style={{
                  background: "rgba(99, 102, 241, 0.1)",
                  borderColor: "rgba(99, 102, 241, 0.3)",
                  color: "#818cf8",
                }}
              >
                ChromaDB
              </span>
              <span
                className="tech-badge badge"
                style={{
                  background: "rgba(16, 185, 129, 0.1)",
                  borderColor: "rgba(16, 185, 129, 0.3)",
                  color: "#10b981",
                }}
              >
                FastAPI
              </span>
            </div>
          </div>
        </aside>

        {/* Main Chat */}
        <main className="chat-main">
          {/* Header */}
          <header className="chat-header">
            <Link href="/" className="chat-header-back">
              ← Back
            </Link>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  background: "var(--gradient-text)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                {repoName}
              </div>
            </div>
            <div className="navbar-badges" style={{ display: "flex" }}>
              <span className="badge badge-langchain">LangGraph RAG</span>
            </div>
          </header>

          {/* Messages */}
          <div className="chat-messages" id="chat-messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">💬</div>
                <div className="empty-state-title">Ask anything about this repo</div>
                <div className="empty-state-desc">
                  GitWise has indexed <strong>{repoName}</strong> and is ready to answer your questions.
                </div>
                <div className="suggestion-chips">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      className="suggestion-chip"
                      onClick={() => sendMessage(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === "user" ? "👤" : "⚡"}
                </div>
                <div className="message-bubble">
                  {msg.role === "assistant" ? (
                    <>
                      {msg.isStreaming && !msg.content ? (
                        <div className="typing-indicator">
                          <div className="typing-dot" />
                          <div className="typing-dot" />
                          <div className="typing-dot" />
                        </div>
                      ) : (
                        <MarkdownContent text={msg.content} />
                      )}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="message-sources">
                          <div className="sources-title">Sources</div>
                          <div className="source-tags">
                            {msg.sources.map((s) => (
                              <span key={s} className="source-tag">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <span>{msg.content}</span>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="chat-input-area">
            <div className="chat-input-row">
              <textarea
                ref={textareaRef}
                id="chat-input"
                className="chat-textarea"
                placeholder="Ask anything about this codebase... (Enter to send, Shift+Enter for new line)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
              />
              <button
                id="send-btn"
                className="btn-send"
                onClick={() => sendMessage(input)}
                disabled={isLoading || !input.trim()}
                title="Send message"
              >
                {isLoading ? "⏳" : "➤"}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
