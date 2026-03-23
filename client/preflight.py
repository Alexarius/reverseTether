"""Preflight checks for ADB connection and llama.cpp server health.

This module validates:
1. ADB device connectivity
2. ADB port forwarding (tcp:8080)
3. llama.cpp server health endpoint

IMPORTANT: The health check uses only non-mutating endpoints (/health)
to avoid warming the model or allocating caches before benchmarks.

The HTTP session used here MUST NOT be reused for benchmarks to avoid
skipping TCP handshake overhead during the first cold run.
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass

import requests


FORWARD_SPEC = "tcp:8080"


@dataclass
class PreflightResult:
    """Result of preflight validation."""

    adb_connected: bool
    port_forwarded: bool
    server_healthy: bool
    error_message: str | None = None


def check_adb_device() -> tuple[bool, str | None]:
    """Check if an ADB device is connected and online.

    Returns:
        Tuple of (success, error_message).
        error_message is None on success.
    """
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, f"ADB command failed: {result.stderr.strip()}"

        # Parse output: skip header line, look for "device" status
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # Skip "List of devices attached"
            if line.strip() and "\tdevice" in line:
                return True, None

        return False, "ADB device offline or not found."

    except FileNotFoundError:
        return False, "ADB not found in PATH. Install Android SDK platform-tools."
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out. Check USB connection."


def check_adb_forward() -> tuple[bool, str | None]:
    """Check if ADB port forwarding is active for tcp:8080.

    Returns:
        Tuple of (success, error_message).
        error_message is None on success.
    """
    try:
        result = subprocess.run(
            ["adb", "forward", "--list"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, f"ADB forward list failed: {result.stderr.strip()}"

        if has_exact_forward_mapping(result.stdout):
            return True, None

        return False, "Port forwarding not active. Run: adb forward tcp:8080 tcp:8080"

    except FileNotFoundError:
        return False, "ADB not found in PATH."
    except subprocess.TimeoutExpired:
        return False, "ADB forward list timed out."


def has_exact_forward_mapping(
    forward_list_output: str,
    local_spec: str = FORWARD_SPEC,
    remote_spec: str = FORWARD_SPEC,
) -> bool:
    """Return True only when adb forward --list contains the exact mapping."""
    for line in forward_list_output.splitlines():
        parts = line.strip().split()
        if len(parts) == 2:
            local, remote = parts
        elif len(parts) >= 3:
            local, remote = parts[1], parts[2]
        else:
            continue

        if local == local_spec and remote == remote_spec:
            return True

    return False


def check_server_health(host: str = "127.0.0.1", port: int = 8080) -> tuple[bool, str | None]:
    """Check if the llama.cpp server is responding on /health.

    Uses a fresh session that is explicitly closed after the check
    to avoid connection reuse artifacts in subsequent benchmarks.

    Args:
        host: Server host (default: 127.0.0.1)
        port: Server port (default: 8080)

    Returns:
        Tuple of (success, error_message).
        error_message is None on success.
    """
    url = f"http://{host}:{port}/health"

    # Use a fresh session and explicitly close it to avoid reuse
    session = requests.Session()
    try:
        response = session.get(url, timeout=5)
        if response.status_code == 200:
            return True, None
        else:
            return False, f"Server /health returned HTTP {response.status_code}"

    except requests.exceptions.ConnectionError:
        return (
            False,
            f"Connection refused on {host}:{port}. "
            "Is the llama.cpp server running on the phone?",
        )
    except requests.exceptions.Timeout:
        return False, f"Server health check timed out ({host}:{port})"
    except requests.exceptions.RequestException as e:
        return False, f"Health check failed: {e}"
    finally:
        # Critical: close session to prevent connection reuse in benchmarks
        session.close()


def run_preflight(
    host: str = "127.0.0.1",
    port: int = 8080,
    skip_adb: bool = False,
) -> PreflightResult:
    """Run all preflight checks.

    Checks are run in order:
    1. ADB device connectivity
    2. ADB port forwarding
    3. Server health endpoint

    If any check fails, subsequent checks are skipped and the result
    reports the first failure.

    Args:
        host: Server host for health check
        port: Server port for health check
        skip_adb: If True, skip ADB checks (for local laptop testing)

    Returns:
        PreflightResult with status of each check.
    """
    result = PreflightResult(
        adb_connected=False,
        port_forwarded=False,
        server_healthy=False,
    )

    # Step 1: Check ADB device (unless skipped for local testing)
    if not skip_adb:
        adb_ok, adb_error = check_adb_device()
        if not adb_ok:
            result.error_message = adb_error
            return result
        result.adb_connected = True

        # Step 2: Check port forwarding
        fwd_ok, fwd_error = check_adb_forward()
        if not fwd_ok:
            result.error_message = fwd_error
            return result
        result.port_forwarded = True
    else:
        # When skipping ADB checks, mark as passed
        result.adb_connected = True
        result.port_forwarded = True

    # Step 3: Check server health
    health_ok, health_error = check_server_health(host, port)
    if not health_ok:
        result.error_message = health_error
        return result
    result.server_healthy = True

    return result


def print_preflight_result(result: PreflightResult) -> None:
    """Print preflight result to stdout/stderr."""
    print("Preflight Check Results")
    print("=" * 40)

    def status_icon(ok: bool) -> str:
        return "[OK]" if ok else "[FAIL]"

    print(f"  ADB Device:      {status_icon(result.adb_connected)}")
    print(f"  Port Forwarding: {status_icon(result.port_forwarded)}")
    print(f"  Server Health:   {status_icon(result.server_healthy)}")
    print("=" * 40)

    if result.error_message:
        print(f"\nError: {result.error_message}", file=sys.stderr)
    elif result.server_healthy:
        print("\nAll preflight checks passed. Ready for benchmark.")


def main() -> None:
    """Run preflight checks as a standalone CLI."""
    parser = argparse.ArgumentParser(
        description="Validate ADB forwarding and llama.cpp server health.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full preflight (ADB + server health)
  python -m client.preflight

  # Skip ADB checks (for local laptop server testing)
  python -m client.preflight --skip-adb
""",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)",
    )
    parser.add_argument(
        "--skip-adb",
        action="store_true",
        help="Skip ADB device and port forwarding checks (for local testing)",
    )

    args = parser.parse_args()
    result = run_preflight(
        host=args.host,
        port=args.port,
        skip_adb=args.skip_adb,
    )
    print_preflight_result(result)

    if not result.server_healthy:
        sys.exit(1)


if __name__ == "__main__":
    main()
