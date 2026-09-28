"""CI eval gate: run each evals/<tier>/*.evalset.json against a fresh MCP server.

Mechanics only enforce the "task success" launch-bar dimension (docs/PROGRESS.md M5.4).
Zero-unauthorized-access, p95 latency, and cost/task have no CI signal yet (blocked on
Modules 6/8) and are not claimed here.

One `adk eval` invocation per tier (test_config.json auto-pickup requires exactly one
evalset file per invocation) and one fresh MCP server subprocess per attempt: a shared,
long-lived server caused idempotency-key collisions and connection-closed flakiness
across separate `adk eval` runs (docs/PROGRESS.md M5.2/M5.3), and two adversarial cases
hardcode a one-time-use idempotency key that a prior run may already have consumed.
A bounded retry (fresh server each time) absorbs the transient OAuth-token-refresh and
MCP-connection-closed failures already documented as occasional, not agent bugs.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

MCP_PORT = 8000
MAX_ATTEMPTS = 3
STARTUP_TIMEOUT_S = 15.0
SHUTDOWN_TIMEOUT_S = 10.0
TRANSIENT_MARKERS = ("oauth2.googleapis.com", "Read timed out", "Connection closed")


class ServerStartupError(RuntimeError):
    pass


def _wait_for_port(port: int, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise ServerStartupError("MCP server exited during startup")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise ServerStartupError("MCP server did not start in time")


def _start_server() -> subprocess.Popen[bytes]:
    proc = subprocess.Popen([sys.executable, "-m", "mcp_server.server"])
    _wait_for_port(MCP_PORT, proc)
    return proc


def _stop_server(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=SHUTDOWN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=SHUTDOWN_TIMEOUT_S)


def run_tier(evalset: Path) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        server = _start_server()
        try:
            result = subprocess.run(  # noqa: S603
                ["uv", "run", "adk", "eval", "hr_agent", str(evalset)],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            _stop_server(server)

        output = result.stdout + result.stderr
        print(output)
        if result.returncode == 0:
            return True

        is_transient = any(marker in output for marker in TRANSIENT_MARKERS)
        if is_transient and attempt < MAX_ATTEMPTS:
            print(f"[{evalset}] transient failure (attempt {attempt}); retrying, fresh server")
            continue
        return False
    return False


def main() -> int:
    tiers = sorted(Path("evals").glob("*/*.evalset.json"))
    if not tiers:
        print("No eval sets found under evals/*/*.evalset.json; skipping.")
        return 0

    failures = [str(tier) for tier in tiers if not run_tier(tier)]

    print("\n--- Launch bar coverage (docs/PROGRESS.md M5.4) ---")
    print("This gate enforces task success only. Zero-unauthorized-access, p95 latency,")
    print("and cost/task are documented targets, not yet enforceable in CI (blocked on")
    print("Module 6 / Module 8).")

    if failures:
        print(f"\nFAILED tiers: {', '.join(failures)}")
        return 1
    print("\nAll tiers passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
