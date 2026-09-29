# Containerizes mcp_server only -- NOT the agent (7.2's "deploy the agent to Cloud Run" was
# skipped by scope decision; the agent stays on Agent Engine). This exists solely so the
# deployed agent has a reachable, IAM-gated HCM_MCP_URL instead of localhost:8000.
#
# Build from the repo root (needs mcp_server/ as build context):
#   docker build -f deploy/cloud_run/mcp_server.Dockerfile -t mcp-server .
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Only mcp_server/requirements.txt, not the project's uv.lock -- see that file's own comment.
COPY mcp_server/requirements.txt mcp_server/requirements.txt
RUN uv pip install --system --no-cache-dir -r mcp_server/requirements.txt

COPY mcp_server/ mcp_server/

# HOST/PORT read by mcp_server/server.py's main(). Cloud Run injects PORT at runtime and
# overrides this default; 8080 matches Cloud Run's own default so `docker run -p 8080:8080`
# behaves the same locally. MCP_ALLOWED_HOSTS is deliberately not set here -- it depends on
# the Cloud Run URL assigned at deploy time, so it's a per-deploy --set-env-vars, not
# something the image can know about itself.
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "mcp_server.server"]
