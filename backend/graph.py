"""
graph.py — LangGraph StateGraph definitions for GitWise.

Two graphs:
  1. IndexingGraph  — clone → chunk → embed → store in ChromaDB
  2. RAGGraph       — embed query → retrieve → build prompt → stream answer
"""

import logging
from typing import TypedDict, Annotated, Any
import operator

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

from config import settings
from repo_handler import load_repo_documents, repo_id_from_url
from vector_store import get_vector_store, collection_exists
from prompts import SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE

logger = logging.getLogger("gitwi.graph")


# ─────────────────────────────────────────────
#  INDEXING GRAPH
# ─────────────────────────────────────────────

class IndexingState(TypedDict):
    repo_url: str
    collection_name: str
    documents: list[Document]
    chunks: list[Document]
    status: str
    error: str
    file_count: int
    chunk_count: int


def clone_and_load_node(state: IndexingState) -> IndexingState:
    """Node 1: Clone the repo and load raw file documents."""
    logger.info(f"[IndexingGraph] Cloning: {state['repo_url']}")
    try:
        docs, _ = load_repo_documents(state["repo_url"])
        return {
            **state,
            "documents": docs,
            "file_count": len(docs),
            "status": "loaded",
        }
    except Exception as e:
        logger.error(f"Clone failed: {e}")
        return {**state, "error": str(e), "status": "error"}


def chunk_documents_node(state: IndexingState) -> IndexingState:
    """Node 2: Split large files into overlapping chunks."""
    logger.info(f"[IndexingGraph] Chunking {len(state['documents'])} documents")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(state["documents"])
    logger.info(f"[IndexingGraph] Created {len(chunks)} chunks")
    return {**state, "chunks": chunks, "chunk_count": len(chunks), "status": "chunked"}


def embed_and_store_node(state: IndexingState) -> IndexingState:
    """Node 3: Embed chunks and persist to ChromaDB."""
    logger.info(f"[IndexingGraph] Embedding {len(state['chunks'])} chunks → ChromaDB")
    try:
        store = get_vector_store(state["collection_name"])
        # Add in batches to respect API rate limits
        batch_size = 50
        chunks = state["chunks"]
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            store.add_documents(batch)
            logger.info(f"  Stored batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
        return {**state, "status": "indexed"}
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return {**state, "error": str(e), "status": "error"}


def build_indexing_graph() -> Any:
    """Construct and compile the LangGraph indexing state machine."""
    graph = StateGraph(IndexingState)

    graph.add_node("clone_and_load", clone_and_load_node)
    graph.add_node("chunk_documents", chunk_documents_node)
    graph.add_node("embed_and_store", embed_and_store_node)

    graph.set_entry_point("clone_and_load")
    graph.add_edge("clone_and_load", "chunk_documents")
    graph.add_edge("chunk_documents", "embed_and_store")
    graph.add_edge("embed_and_store", END)

    return graph.compile()


# ─────────────────────────────────────────────
#  RAG GRAPH
# ─────────────────────────────────────────────

class RAGState(TypedDict):
    repo_url: str
    collection_name: str
    question: str
    chat_history: list[dict]
    retrieved_docs: list[Document]
    context: str
    answer: str
    error: str


def retrieve_context_node(state: RAGState) -> RAGState:
    """Node 1: Retrieve top-k relevant code chunks from ChromaDB."""
    logger.info(f"[RAGGraph] Retrieving context for: {state['question'][:80]}")
    try:
        store = get_vector_store(state["collection_name"])
        retriever = store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.TOP_K_RETRIEVAL},
        )
        docs = retriever.invoke(state["question"])

        # Build a readable context string with file paths
        context_parts = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            lang = doc.metadata.get("language", "")
            context_parts.append(
                f"### File: `{source}`\n```{lang}\n{doc.page_content}\n```"
            )
        context = "\n\n".join(context_parts)

        return {**state, "retrieved_docs": docs, "context": context}
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {**state, "error": str(e), "context": ""}


def generate_answer_node(state: RAGState) -> RAGState:
    """Node 2: Generate answer using Gemini with retrieved context."""
    logger.info(f"[RAGGraph] Generating answer")
    try:
        llm = ChatGroq(
            model=settings.CHAT_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.2,
            streaming=True,
        )

        # Build chat history for context
        history_text = ""
        for msg in state.get("chat_history", [])[-6:]:  # Last 3 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_text += f"**{role.capitalize()}**: {content}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", RAG_PROMPT_TEMPLATE),
        ])

        chain = prompt | llm | StrOutputParser()
        answer = chain.invoke({
            "context": state["context"],
            "chat_history": history_text or "No previous conversation.",
            "question": state["question"],
        })

        return {**state, "answer": answer}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return {**state, "error": str(e), "answer": f"Error generating answer: {e}"}


def build_rag_graph() -> Any:
    """Construct and compile the LangGraph RAG state machine."""
    graph = StateGraph(RAGState)

    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.set_entry_point("retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


# Pre-compile graphs at module load
indexing_graph = build_indexing_graph()
rag_graph = build_rag_graph()
