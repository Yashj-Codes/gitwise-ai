# GitWise 🧠

> AI-Powered GitHub Repository Intelligence — Chat with any codebase in seconds.

Built with **LangChain + LangGraph + Google Gemini (free) + ChromaDB + FastAPI + Next.js**

---

## ✨ What it does

Paste any GitHub repo URL → GitWise clones it, chunks all the code, embeds it into a local vector database, and lets you ask natural language questions about the codebase with streaming AI responses.

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agentic Orchestration** | LangGraph `StateGraph` |
| **RAG Pipeline** | LangChain (loaders, splitters, retrieval chains) |
| **LLM + Embeddings** | Google Gemini 1.5 Flash (FREE) |
| **Vector Database** | ChromaDB (local, persistent) |
| **Backend** | FastAPI + Python (async, streaming SSE) |
| **Frontend** | Next.js 14 (App Router, TypeScript) |
| **Git Cloning** | GitPython |

---

## 🚀 Quick Start

### 1. Get a Free Google API Key

Visit [aistudio.google.com](https://aistudio.google.com/app/apikey) → Create API Key → Copy it.

✅ **Completely free** — 1,000+ requests/day, no credit card required.

### 2. Set Up Environment

```bash
cd gitwi
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Start the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
# → Backend running at http://localhost:8001
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
# → Frontend running at http://localhost:3000
```

### 5. Use GitWise

1. Open [http://localhost:3000](http://localhost:3000)
2. Paste a GitHub repo URL (e.g., `https://github.com/tiangolo/fastapi`)
3. Click **Analyze Repo** — wait for indexing (takes 1-3 min for first time)
4. Ask anything! "What does this repo do?" / "Explain the main architecture"

---

## 🧠 How It Works

```
GitHub URL
    ↓
[LangGraph Indexing Graph]
  Node 1: clone_and_load  → GitPython clones repo, loads all text files
  Node 2: chunk_documents → LangChain RecursiveCharacterTextSplitter
  Node 3: embed_and_store → Gemini embedding-001 → ChromaDB

User Question
    ↓
[LangGraph RAG Graph]
  Node 1: retrieve_context → ChromaDB similarity search (top-8 chunks)
  Node 2: generate_answer  → Gemini 1.5 Flash with context → Streaming SSE

Streamed tokens → Next.js frontend → Real-time chat UI
```

---

## 📁 Project Structure

```
gitwi/
├── backend/
│   ├── main.py          # FastAPI app (streaming endpoints)
│   ├── graph.py         # LangGraph IndexingGraph + RAGGraph
│   ├── repo_handler.py  # Git clone + file parsing
│   ├── vector_store.py  # ChromaDB wrapper
│   ├── prompts.py       # System prompts
│   ├── config.py        # Settings (pydantic-settings)
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── page.tsx           # Landing page
│       └── chat/[repo]/       # Chat interface
├── .env.example
└── README.md
```

---

## 🔑 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Health check |
| `POST` | `/api/index` | Index a GitHub repo (SSE stream) |
| `POST` | `/api/chat` | Chat with indexed repo (SSE stream) |
| `GET`  | `/api/status/{repo_id}` | Check if repo is indexed |

---

## 💾 Local Storage

All data is stored locally — no cloud dependencies:
- Cloned repos: `~/.gitwi/repos/`
- ChromaDB embeddings: `~/.gitwi/chroma/`

---

## 📄 License

MIT
