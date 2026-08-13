import sys
import os
import uvicorn

# Add backend directory to path so it can find its modules
sys.path.insert(0, os.path.abspath("backend"))

from backend.main import app

if __name__ == "__main__":
    # Hugging Face Spaces exposes port 7860
    uvicorn.run("backend.main:app", host="0.0.0.0", port=7860)
