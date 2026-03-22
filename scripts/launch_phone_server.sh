#!/usr/bin/env bash
#
# launch_phone_server.sh
# Wrapper script for launching llama.cpp server on Samsung Galaxy S25 Ultra
#
# Usage:
#   ./scripts/launch_phone_server.sh [--gpu|--cpu] [--model <path>]
#
# This script ensures reproducible server launches with consistent flags.

set -euo pipefail

# ==============================================================================
# Configuration (modify these as needed for your environment)
# ==============================================================================

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-$HOME/llama.cpp}"
DEFAULT_MODEL_PATH="${LLAMA_CPP_DIR}/models/Llama-3.2-1B-Instruct-Q4_0-GGUF"

# Fixed settings per EXPERIMENT_PROTOCOL.md
CONTEXT_LENGTH=2048
SERVER_PORT=8080
SERVER_HOST="127.0.0.1"

# ==============================================================================
# Parse arguments
# ==============================================================================

BACKEND="cpu"
MODEL_PATH="${DEFAULT_MODEL_PATH}"
VERBOSE=0

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Launch llama.cpp server with reproducible settings."
    echo ""
    echo "Options:"
    echo "  --cpu          CPU-only mode (default, -ngl 0)"
    echo "  --gpu          GPU/OpenCL mode (-ngl 99)"
    echo "  --model PATH   Path to GGUF model file"
    echo "  --verbose      Print detailed launch info"
    echo "  --help         Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  LLAMA_CPP_DIR  Path to llama.cpp directory (default: ~/llama.cpp)"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --cpu)
            BACKEND="cpu"
            shift
            ;;
        --gpu)
            BACKEND="gpu"
            shift
            ;;
        --model)
            MODEL_PATH="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            print_usage
            exit 1
            ;;
    esac
done

# ==============================================================================
# Validation
# ==============================================================================

SERVER_BIN="${LLAMA_CPP_DIR}/build/bin/llama-server"

if [[ ! -x "${SERVER_BIN}" ]]; then
    echo "Error: Server binary not found at ${SERVER_BIN}" >&2
    echo "Ensure llama.cpp is built. See docs/phone_server_runbook.md" >&2
    exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "Error: Model file not found at ${MODEL_PATH}" >&2
    exit 1
fi

# ==============================================================================
# Set GPU offload layers based on backend
# ==============================================================================

if [[ "${BACKEND}" == "gpu" ]]; then
    NGL=99
else
    NGL=0
fi

# ==============================================================================
# Log launch configuration
# ==============================================================================

echo "========================================"
echo "llama.cpp Server Launch"
echo "========================================"
echo "Timestamp:       $(date -Iseconds)"
echo "Backend:         ${BACKEND}"
echo "Model:           ${MODEL_PATH}"
echo "Context length:  ${CONTEXT_LENGTH}"
echo "GPU layers:      ${NGL}"
echo "Host:            ${SERVER_HOST}"
echo "Port:            ${SERVER_PORT}"
echo "========================================"

if [[ ${VERBOSE} -eq 1 ]]; then
    echo ""
    echo "Full command:"
    echo "  LD_LIBRARY_PATH=/vendor/lib64 ${SERVER_BIN} \\"
    echo "    -m ${MODEL_PATH} \\"
    echo "    -c ${CONTEXT_LENGTH} \\"
    echo "    --port ${SERVER_PORT} \\"
    echo "    --host ${SERVER_HOST} \\"
    echo "    -ngl ${NGL}"
    echo ""
fi

# ==============================================================================
# Launch server
# ==============================================================================

# LD_LIBRARY_PATH must be set to access Android vendor libraries
export LD_LIBRARY_PATH=/vendor/lib64

exec "${SERVER_BIN}" \
    -m "${MODEL_PATH}" \
    -c "${CONTEXT_LENGTH}" \
    --port "${SERVER_PORT}" \
    --host "${SERVER_HOST}" \
    -ngl "${NGL}"
