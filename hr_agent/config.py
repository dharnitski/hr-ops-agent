import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Default keeps import working without secrets (unit tests, CI); override via MODEL_ID in .env.
# TODO: retest gemini-3.8-flash (slow on 2026-09-25; see .env.example)
DEFAULT_MODEL_ID = "gemini-3.5-flash-lite"
DEFAULT_HCM_MCP_URL = "http://localhost:8000/mcp"

MODEL_ID = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
HCM_MCP_URL = os.environ.get("HCM_MCP_URL", DEFAULT_HCM_MCP_URL)
