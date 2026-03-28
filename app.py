# Email Triage OpenEnv - Root App Entry Point
# This file re-exports the FastAPI app for Hugging Face Spaces compatibility

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
