"""Framework-free MCP client: proves the HCM server contract stands alone.

Imports nothing from hr_agent/ or mcp_server/. Start the server first:
    uv run python -m mcp_server.server
Then: uv run python scratch/mcp_client.py
"""

import asyncio
import os
import uuid
from typing import Any

from mcp import Client

URL = os.environ.get("HCM_MCP_URL", "http://localhost:8000/mcp")


async def call(client: Client, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Return structuredContent, tagging failures that arrive outside it."""
    try:
        result = await client.call_tool(name, args)
    except Exception as exc:  # protocol-level rejection (JSON-RPC error)
        return {"transport_error": f"{type(exc).__name__}: {exc}"}
    if result.is_error:  # tool-level failure (e.g. schema validation ToolError)
        text = " ".join(getattr(c, "text", "") for c in result.content)
        return {"is_error": True, "text": text}
    structured = result.structured_content or {}
    # Union return types are published wrapped as {"result": ...}.
    return structured.get("result", structured)


def check(ok: bool, label: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        raise SystemExit(1)


async def main() -> None:
    async with Client(URL) as client:
        print("== tools")
        for tool in (await client.list_tools()).tools:
            props = list((tool.input_schema or {}).get("properties", {}))
            print(f"{tool.name}: args={props} outputSchema={'yes' if tool.output_schema else 'no'}")

        print("\n== get_employee")
        print("valid  :", await call(client, "get_employee", {"employee_id": "E1002"}))
        print("unknown:", await call(client, "get_employee", {"employee_id": "E9999"}))
        print("malformed:", await call(client, "get_employee", {"employee_id": "bob"}))

        print("\n== submit_pto_request idempotency")
        key = f"demo-{uuid.uuid4()}"
        args = {
            "employee_id": "E1002",
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "idempotency_key": key,
        }
        first = await call(client, "submit_pto_request", args)
        second = await call(client, "submit_pto_request", args)
        print("first   :", first)
        print("replay  :", second)
        check(second.get("replayed") is True, "replay flagged")
        check(second.get("request_id") == first.get("request_id"), "same request_id")

        conflict = await call(client, "submit_pto_request", {**args, "end_date": "2026-10-15"})
        print("conflict:", conflict)
        check(conflict.get("code") == "idempotency_conflict", "conflict detected")

        print("\n== unknown argument")
        print(await call(client, "get_employee", {"employee_id": "E1002", "salary": True}))


if __name__ == "__main__":
    asyncio.run(main())
