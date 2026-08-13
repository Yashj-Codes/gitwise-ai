"""
repo_handler.py — Clone and parse GitHub repositories into LangChain Documents.
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Generator

import git
from langchain_core.documents import Document

from config import settings

logger = logging.getLogger("gitwi.repo")

# Files/dirs to completely skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".mypy_cache",
    ".pytest_cache", ".tox", "vendor", "Pods",
}

SKIP_EXTENSIONS = {
    # Binary / media
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Archives
    ".zip", ".tar", ".gz", ".rar", ".7z",
    # Lock files (noisy, low value)
    ".lock",
    # Compiled
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe",
    # Misc
    ".DS_Store", ".min.js", ".min.css",
}

MAX_FILE_BYTES = 150_000  # Skip files > 150 KB
MAX_TOTAL_FILES = 500


def repo_id_from_url(url: str) -> str:
    """Convert a GitHub URL to a safe, unique identifier."""
    url = url.rstrip("/").replace("https://github.com/", "").replace("/", "_")
    url = re.sub(r"[^\w\-]", "_", url)
    short_hash = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{url}_{short_hash}"


def clone_or_update_repo(url: str) -> Path:
    """Clone the repo if not exists, else pull latest."""
    repo_id = repo_id_from_url(url)
    repo_path = Path(settings.REPOS_DIR) / repo_id

    if repo_path.exists():
        logger.info(f"Repo exists, pulling latest: {repo_path}")
        try:
            repo = git.Repo(repo_path)
            repo.remotes.origin.pull()
        except Exception as e:
            logger.warning(f"Pull failed ({e}), using cached version.")
    else:
        logger.info(f"Cloning {url} → {repo_path}")
        clone_url = url
        if settings.GITHUB_TOKEN:
            # Inject token for higher rate limits
            clone_url = url.replace(
                "https://github.com",
                f"https://{settings.GITHUB_TOKEN}@github.com",
            )
        git.Repo.clone_from(clone_url, repo_path, depth=1)

    return repo_path


def iter_repo_files(repo_path: Path) -> Generator[Path, None, None]:
    """Yield readable text files from the repo, respecting limits."""
    count = 0
    for root, dirs, files in os.walk(repo_path):
        # Prune skip dirs in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in files:
            if count >= MAX_TOTAL_FILES:
                return
            fpath = Path(root) / fname
            if fpath.suffix.lower() in SKIP_EXTENSIONS:
                continue
            if fpath.stat().st_size > MAX_FILE_BYTES:
                continue
            count += 1
            yield fpath


def load_repo_documents(url: str) -> tuple[list[Document], Path]:
    """
    Clone the repo and return a list of LangChain Documents (one per file).
    Each Document metadata includes: source, file_path, language, repo_url.
    """
    repo_path = clone_or_update_repo(url)
    documents: list[Document] = []

    for fpath in iter_repo_files(repo_path):
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue
            rel_path = str(fpath.relative_to(repo_path))
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": rel_path,
                        "file_path": str(fpath),
                        "repo_url": url,
                        "language": fpath.suffix.lstrip(".") or "txt",
                    },
                )
            )
        except Exception as e:
            logger.warning(f"Skipping {fpath}: {e}")

    logger.info(f"Loaded {len(documents)} documents from {url}")
    return documents, repo_path
