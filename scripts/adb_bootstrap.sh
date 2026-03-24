#!/usr/bin/env bash
#
# adb_bootstrap.sh
# Establish ADB port forwarding for reverse-tethered llama.cpp benchmark
#
# Usage:
#   ./scripts/adb_bootstrap.sh
#
# This script:
#   1. Verifies an ADB device is connected
#   2. Sets up tcp:8080 -> tcp:8080 port forwarding
#   3. Validates the forwarding rule is active
#
# Prerequisites:
#   - ADB installed and in PATH
#   - Phone connected via USB with USB debugging enabled
#   - llama.cpp server ready to launch on the phone (not started by this script)

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

FORWARD_PORT=8080
EXPECTED_FORWARD="tcp:${FORWARD_PORT} tcp:${FORWARD_PORT}"

# ==============================================================================
# ADB Binary Resolution
# ==============================================================================

# Allow override via environment variable
if [[ -n "${ADB_BIN:-}" ]]; then
    if ! command -v "${ADB_BIN}" &> /dev/null; then
        echo "Error: ADB_BIN='${ADB_BIN}' not found or not executable" >&2
        exit 1
    fi
elif command -v adb &> /dev/null; then
    ADB_BIN="adb"
elif command -v adb.exe &> /dev/null; then
    ADB_BIN="adb.exe"
else
    echo "Error: ADB not found in PATH" >&2
    echo "Install Android SDK platform-tools and add to PATH" >&2
    echo "Or set ADB_BIN environment variable to the full path" >&2
    exit 1
fi

echo "Using ADB binary: ${ADB_BIN}"

# ==============================================================================
# Check device connection
# ==============================================================================

echo "Checking ADB device connection..."

DEVICE_COUNT=$("${ADB_BIN}" devices | grep -c "device$" || true)

if [[ "${DEVICE_COUNT}" -eq 0 ]]; then
    echo "Error: No ADB device found" >&2
    echo "" >&2
    echo "Troubleshooting:" >&2
    echo "  1. Ensure phone is connected via USB" >&2
    echo "  2. Enable USB debugging in Developer Options" >&2
    echo "  3. Accept the USB debugging prompt on the phone" >&2
    echo "  4. Run 'adb devices' to verify connection" >&2
    exit 1
fi

if [[ "${DEVICE_COUNT}" -gt 1 ]]; then
    echo "Warning: Multiple ADB devices found. Using default." >&2
    "${ADB_BIN}" devices
fi

echo "  Device connected: OK"

# ==============================================================================
# Remove existing forwarding rule (if any)
# ==============================================================================

# Remove any existing forward for this port to ensure clean state
"${ADB_BIN}" forward --remove tcp:${FORWARD_PORT} 2>/dev/null || true

# ==============================================================================
# Set up port forwarding
# ==============================================================================

echo "Setting up port forwarding tcp:${FORWARD_PORT} -> tcp:${FORWARD_PORT}..."

if ! "${ADB_BIN}" forward tcp:${FORWARD_PORT} tcp:${FORWARD_PORT}; then
    echo "Error: Failed to set up port forwarding" >&2
    exit 1
fi

echo "  Port forwarding: OK"

# ==============================================================================
# Verify forwarding rule
# ==============================================================================

echo "Verifying forwarding rule..."

FORWARD_LIST=$("${ADB_BIN}" forward --list)

if echo "${FORWARD_LIST}" | grep -Eq "^(\\S+[[:space:]]+)?tcp:${FORWARD_PORT}[[:space:]]+tcp:${FORWARD_PORT}$"; then
    echo "  Verification: OK"
else
    echo "Error: Port forwarding verification failed" >&2
    echo "Expected mapping: ${EXPECTED_FORWARD}" >&2
    echo "Forward list:" >&2
    echo "${FORWARD_LIST}" >&2
    exit 1
fi

# ==============================================================================
# Summary
# ==============================================================================

echo ""
echo "========================================"
echo "ADB Bootstrap Complete"
echo "========================================"
echo "Port ${FORWARD_PORT} is now forwarded to the phone."
echo ""
echo "Next steps:"
echo "  1. Start llama.cpp server on the phone (see docs/phone_server_runbook.md)"
echo "  2. Run preflight check: python -m client.preflight"
echo "  3. Run benchmark: python -m client.cli ..."
echo ""
