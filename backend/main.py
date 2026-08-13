"""
main.py — FastAPI application for GitWise backend.

Endpoints:
  POST /api/index  — Index a GitHub repo (streaming progress)
  POST /api/chat   — Chat with an indexed repo (streaming SSE)
  GET  /api/status/{repo_id} — Check if a repo is indexed
  GET  /           — Health check
"""

import asyncio
import json
import logging
import sys
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl

from config import settings
from repo_handler import repo_id_from_url
from vector_store import collection_exists, delete_collection
from graph import indexing_graph, rag_graph

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gitwi.main")

# ── App ──────────────────────────────────────
app = FastAPI(
    title="GitWise API",
    description="AI-powered GitHub repository Q&A using LangChain + LangGraph + Gemini",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ─────────────────

class IndexRequest(BaseModel):
    repo_url: str
    force_reindex: bool = False


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    repo_url: str
    messages: list[ChatMessage]


# ── SSE helper ───────────────────────────────

def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Routes ───────────────────────────────────

@app.get("/")
async def health():
    return {
        "service": "GitWise API",
        "status": "running",
        "version": "1.0.0",
        "stack": ["LangChain", "LangGraph", "Gemini", "ChromaDB", "FastAPI"],
    }


@app.get("/api/status/{repo_id}")
async def check_status(repo_id: str):
    """Check if a repo collection is already indexed."""
    is_indexed = collection_exists(repo_id)
    return {"repo_id": repo_id, "indexed": is_indexed}


@app.post("/api/index")
async def index_repository(req: IndexRequest):
    """
    Clone and index a GitHub repository.
    Returns a streaming SSE response with progress updates.
    """
    repo_url = req.repo_url.strip().rstrip("/")
    collection_name = repo_id_from_url(repo_url)

    async def event_stream() -> AsyncGenerator[str, None]:
        yield sse_event({"type": "start", "message": f"Starting indexing for {repo_url}"})
        await asyncio.sleep(0.1)

        # Check if already indexed
        if collection_exists(collection_name) and not req.force_reindex:
            yield sse_event({
                "type": "done",
                "message": "Repository already indexed! Ready to chat.",
                "repo_id": collection_name,
                "cached": True,
            })
            return

        # Force re-index: delete existing collection
        if req.force_reindex:
            yield sse_event({"type": "progress", "message": "Clearing previous index..."})
            delete_collection(collection_name)

        yield sse_event({"type": "progress", "message": "Cloning repository..."})
        await asyncio.sleep(0.1)

        # Run the LangGraph indexing pipeline in a thread (blocking I/O)
        initial_state = {
            "repo_url": repo_url,
            "collection_name": collection_name,
            "documents": [],
            "chunks": [],
            "status": "starting",
            "error": "",
            "file_count": 0,
            "chunk_count": 0,
        }

        try:
            result = await asyncio.to_thread(
                indexing_graph.invoke, initial_state
            )

            if result.get("status") == "error":
                yield sse_event({
                    "type": "error",
                    "message": result.get("error", "Unknown error during indexing"),
                })
                return

            yield sse_event({
                "type": "progress",
                "message": f"Loaded {result['file_count']} files",
            })
            await asyncio.sleep(0.1)

            yield sse_event({
                "type": "progress",
                "message": f"Created {result['chunk_count']} chunks, embedding now...",
            })
            await asyncio.sleep(0.1)

            yield sse_event({
                "type": "done",
                "message": "Repository indexed successfully! You can now ask questions.",
                "repo_id": collection_name,
                "file_count": result["file_count"],
                "chunk_count": result["chunk_count"],
                "cached": False,
            })

        except Exception as e:
            logger.exception("Indexing pipeline error")
            yield sse_event({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat_with_repo(req: ChatRequest):
    """
    Ask a question about an indexed repository.
    Returns a streaming SSE response with the AI answer.
    """
    repo_url = req.repo_url.strip().rstrip("/")
    collection_name = repo_id_from_url(repo_url)

    if not collection_exists(collection_name):
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_url}' has not been indexed yet. Please index it first.",
        )

    # Extract latest user question
    messages = req.messages
    question = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )
    if not question:
        raise HTTPException(status_code=400, detail="No user message found.")

    # Build chat history (all messages except last user msg)
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in messages[:-1]
    ]

    async def event_stream() -> AsyncGenerator[str, None]:
        initial_state = {
            "repo_url": repo_url,
            "collection_name": collection_name,
            "question": question,
            "chat_history": chat_history,
            "retrieved_docs": [],
            "context": "",
            "answer": "",
            "error": "",
        }

        try:
            result = await asyncio.to_thread(rag_graph.invoke, initial_state)

            if result.get("error"):
                yield sse_event({"type": "error", "message": result["error"]})
                return

            # Stream the answer token by token
            answer = result.get("answer", "")
            sources = [
                doc.metadata.get("source", "")
                for doc in result.get("retrieved_docs", [])
                if doc.metadata.get("source")
            ]
            unique_sources = list(dict.fromkeys(sources))  # preserve order, deduplicate

            # Stream in word-level chunks for a smoother UX
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield sse_event({"type": "token", "content": chunk})
                await asyncio.sleep(0.01)  # tiny delay for streaming effect

            yield sse_event({
                "type": "done",
                "sources": unique_sources[:8],
            })

        except Exception as e:
            logger.exception("Chat pipeline error")
            yield sse_event({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Entry Point ───────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level="info",
    )
