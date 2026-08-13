"""
vector_store.py — ChromaDB wrapper for per-repo persistent vector collections.
"""

import logging
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

logger = logging.getLogger("gitwi.vectorstore")

# Single persistent ChromaDB client
_chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DIR)


def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
    )


def get_vector_store(collection_name: str) -> Chroma:
    """Return a LangChain Chroma vector store for the given collection."""
    return Chroma(
        client=_chroma_client,
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
    )


def collection_exists(collection_name: str) -> bool:
    """Check whether a repo has already been indexed."""
    try:
        col = _chroma_client.get_collection(collection_name)
        return col.count() > 0
    except Exception:
        return False


def delete_collection(collection_name: str) -> None:
    """Delete an existing collection (re-index from scratch)."""
    try:
        _chroma_client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
    except Exception as e:
        logger.warning(f"Could not delete collection {collection_name}: {e}")
