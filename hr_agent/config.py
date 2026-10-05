import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Module 8.1: ADK defaults to putting full prompts, tool args and tool results (PTO balances
# included) on trace spans, unless `adk deploy --otel_to_cloud` happens to set this to false.
# Default it off for every entry point (adk web/run, tests, deploy); set it to true in .env
# only to debug a specific trace, never in a deployed env file (M4.4).
os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

# Default keeps import working without secrets (unit tests, CI); override via MODEL_ID in .env.
# TODO: retest gemini-3.8-flash (slow on 2026-09-25; see .env.example)
DEFAULT_MODEL_ID = "gemini-3.5-flash-lite"
DEFAULT_HCM_MCP_URL = "http://localhost:8000/mcp"

MODEL_ID = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
HCM_MCP_URL = os.environ.get("HCM_MCP_URL", DEFAULT_HCM_MCP_URL)

# Empty (default) means "no service-to-service auth needed" -- local mcp_server has no IAM
# in front of it. Set to the Cloud Run service's base URL to enable ID-token auth
# (hr_agent/toolsets.py); never leave this literally set to an empty string in a real
# deploy's env file (Agent Engine's deploy API hard-fails on empty-valued vars -- M7.1).
HCM_MCP_AUDIENCE = os.environ.get("HCM_MCP_AUDIENCE", "")
