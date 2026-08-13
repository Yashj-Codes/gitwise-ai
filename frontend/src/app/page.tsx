"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";

const EXAMPLE_REPOS = [
  "https://github.com/tiangolo/fastapi",
  "https://github.com/vercel/next.js",
  "https://github.com/langchain-ai/langchain",
];

const FEATURES = [
  {
    icon: "🧠",
    title: "LangGraph Agentic RAG",
    desc: "Powered by a LangGraph StateGraph that orchestrates cloning, chunking, embedding, and retrieval as a state machine.",
  },
  {
    icon: "🔗",
    title: "LangChain Pipeline",
    desc: "Uses LangChain document loaders, text splitters, and retrieval chains for production-grade RAG.",
  },
  {
    icon: "⚡",
    title: "Gemini 1.5 Flash",
    desc: "Google's fastest model for both embeddings and chat — completely free with 1,000+ requests/day.",
  },
  {
    icon: "🗃️",
    title: "ChromaDB Vector Store",
    desc: "Persistent local vector database stores your repo embeddings so you never re-index unnecessarily.",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [status, setStatus] = useState<
    | { type: "idle" }
    | { type: "indexing"; message: string; progress: number }
    | { type: "success"; message: string; repoId: string }
    | { type: "error"; message: string }
  >({ type: "idle" });

  const isLoading = status.type === "indexing";

  async function handleIndex(e: React.FormEvent) {
    e.preventDefault();
    if (!repoUrl.trim()) return;

    const url = repoUrl.trim().replace(/\/$/, "");

    setStatus({ type: "indexing", message: "Connecting to server...", progress: 5 });

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const res = await fetch(`${apiUrl}/api/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split("\n").filter((l) => l.startsWith("data:"));

        for (const line of lines) {
          const json = line.replace("data: ", "").trim();
          if (!json) continue;
          const event = JSON.parse(json);

          if (event.type === "start") {
            setStatus({ type: "indexing", message: event.message, progress: 10 });
          } else if (event.type === "progress") {
            setStatus((prev) => ({
              type: "indexing",
              message: event.message,
              progress: prev.type === "indexing" ? Math.min(prev.progress + 25, 85) : 30,
            }));
          } else if (event.type === "done") {
            setStatus({
              type: "success",
              message: event.message,
              repoId: event.repo_id,
            });
            // Navigate to chat after a short delay
            setTimeout(() => {
              const encoded = encodeURIComponent(url);
              router.push(`/chat/${encoded}`);
            }, 800);
          } else if (event.type === "error") {
            setStatus({ type: "error", message: event.message });
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus({ type: "error", message: `Failed to connect: ${msg}. Is the backend running?` });
    }
  }

  return (
    <div className="page-wrapper">
      <div className="bg-animated" />

      {/* Navbar */}
      <nav className="navbar">
        <a href="/" className="navbar-logo">
          <div className="navbar-logo-icon">⚡</div>
          <span className="navbar-logo-text">GitWise</span>
        </a>
        <div className="navbar-badges">
          <span className="badge badge-langchain">LangChain</span>
          <span className="badge badge-langgraph">LangGraph</span>
          <span className="badge badge-gemini">Gemini</span>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="hero-eyebrow">
          <span className="dot" />
          AI-Powered Code Intelligence
        </div>

        <h1 className="hero-title">
          Chat with any{" "}
          <span className="gradient-word">GitHub Repo</span>{" "}
          instantly
        </h1>

        <p className="hero-subtitle">
          Paste a GitHub URL. GitWise clones, indexes, and lets you ask anything
          about the codebase — powered by LangGraph + LangChain + Gemini.
        </p>

        {/* Repo Input Card */}
        <form onSubmit={handleIndex} id="repo-form">
          <div className="repo-input-card">
            <label className="input-label" htmlFor="repo-url-input">
              GitHub Repository URL
            </label>
            <div className="input-row">
              <input
                id="repo-url-input"
                className="repo-input"
                type="url"
                placeholder="https://github.com/username/repository"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                disabled={isLoading}
                required
              />
              <button
                id="index-btn"
                className="btn-primary"
                type="submit"
                disabled={isLoading || !repoUrl.trim()}
              >
                {isLoading ? (
                  <>
                    <span style={{ animation: "typingBounce 1.4s ease-in-out infinite" }}>⏳</span>
                    Indexing...
                  </>
                ) : (
                  <>⚡ Analyze Repo</>
                )}
              </button>
            </div>

            {/* Progress */}
            {status.type === "indexing" && (
              <>
                <div className="progress-bar-wrap">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${status.progress}%` }}
                  />
                </div>
                <div className="status-message">
                  <span>⚙️</span> {status.message}
                </div>
              </>
            )}

            {status.type === "success" && (
              <div className="status-message success">
                ✅ {status.message} — redirecting to chat...
              </div>
            )}

            {status.type === "error" && (
              <div className="status-message error">
                ❌ {status.message}
              </div>
            )}
          </div>
        </form>

        {/* Example repos */}
        <div style={{ marginTop: 20 }}>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 10 }}>
            Try an example:
          </p>
          <div className="suggestion-chips">
            {EXAMPLE_REPOS.map((r) => (
              <button
                key={r}
                className="suggestion-chip"
                onClick={() => setRepoUrl(r)}
                disabled={isLoading}
                type="button"
              >
                {r.replace("https://github.com/", "")}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <div className="features-grid" style={{ marginBottom: 80 }}>
        {FEATURES.map((f) => (
          <div key={f.title} className="feature-card">
            <div className="feature-icon">{f.icon}</div>
            <div className="feature-title">{f.title}</div>
            <div className="feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
