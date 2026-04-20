#!/usr/bin/env bash
#
# capture_phone_metadata.sh
# Capture device and runtime metadata for benchmark reproducibility
#
# Usage:
#   ./scripts/capture_phone_metadata.sh [server options] > metadata.json
#
# Outputs JSON to stdout. Errors/warnings go to stderr.

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-$HOME/llama.cpp}"
DEFAULT_MODEL_PATH="${LLAMA_CPP_DIR}/models/Llama-3.2-1B-Instruct-Q4_0-GGUF"
DEFAULT_CONTEXT_LENGTH=2048
DEFAULT_PORT=8080
DEFAULT_HOST="127.0.0.1"
DEFAULT_CPU_GPU_LAYERS=0
DEFAULT_GPU_OPENCL_LAYERS=99

SERVER_BACKEND="${SERVER_BACKEND:-auto}"
SERVER_MODEL_PATH="${SERVER_MODEL_PATH:-${DEFAULT_MODEL_PATH}}"
SERVER_CONTEXT_LENGTH="${SERVER_CONTEXT_LENGTH:-${DEFAULT_CONTEXT_LENGTH}}"
SERVER_GPU_LAYERS="${SERVER_GPU_LAYERS:-}"
SERVER_PORT="${SERVER_PORT:-${DEFAULT_PORT}}"
SERVER_HOST="${SERVER_HOST:-${DEFAULT_HOST}}"
CAPTURE_PHASE="${CAPTURE_PHASE:-pre_run}"
BACKGROUND_APPS_MINIMIZED="${BACKGROUND_APPS_MINIMIZED:-}"
KNOWN_ANOMALIES="${KNOWN_ANOMALIES:-}"
MANUAL_OBSERVATIONS="${MANUAL_OBSERVATIONS:-}"

# ==============================================================================
# Helper functions
# ==============================================================================

# Safely get value or return "unknown"
safe_read() {
    local file="$1"
    if [[ -r "${file}" ]]; then
        cat "${file}" 2>/dev/null | tr -d '\n' || echo "unknown"
    else
        echo "unknown"
    fi
}

warn() {
    echo "Warning: $*" >&2
}

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Capture phone-side reproducibility metadata as JSON."
    echo ""
    echo "If a llama-server process is running, server launch settings are auto-detected"
    echo "from /proc. Otherwise the script falls back to the configured/default values."
    echo ""
    echo "Options:"
    echo "  --cpu                 Record CPU baseline settings"
    echo "  --gpu                 Record GPU/OpenCL settings"
    echo "  --npu-experimental    Record exploratory NPU settings"
    echo "  --backend VALUE       Explicit backend: cpu|gpu_opencl|npu_experimental"
    echo "  --model PATH          Explicit model path"
    echo "  --context-length N    Explicit context length"
    echo "  --gpu-layers N        Explicit -ngl value"
    echo "  --port N              Explicit server port"
    echo "  --host HOST           Explicit bind host"
    echo "  --phase VALUE         Metadata phase: pre_run|post_run|snapshot"
    echo "  --background-apps-minimized VALUE"
    echo "                         true|false if manually checked before capture"
    echo "  --known-anomalies TEXT"
    echo "                         Known anomalies affecting interpretation"
    echo "  --manual-observations TEXT"
    echo "                         Free-form manual observation notes"
    echo "  --help                Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  LLAMA_CPP_DIR         Path to llama.cpp directory (default: ~/llama.cpp)"
    echo "  SERVER_BACKEND        cpu|gpu_opencl|npu_experimental|auto"
    echo "  SERVER_MODEL_PATH     Path to GGUF model file"
    echo "  SERVER_CONTEXT_LENGTH Context length (-c)"
    echo "  SERVER_GPU_LAYERS     GPU offload layers (-ngl)"
    echo "  SERVER_PORT           Server port"
    echo "  SERVER_HOST           Server bind host"
    echo "  CAPTURE_PHASE         pre_run|post_run|snapshot"
    echo "  BACKGROUND_APPS_MINIMIZED true|false when known"
    echo "  KNOWN_ANOMALIES       Known anomalies affecting interpretation"
    echo "  MANUAL_OBSERVATIONS   Free-form manual observation notes"
}

json_escape() {
    local value="${1-}"
    value=${value//\\/\\\\}
    value=${value//\"/\\\"}
    value=${value//$'\n'/\\n}
    value=${value//$'\r'/\\r}
    value=${value//$'\t'/\\t}
    printf '%s' "${value}"
}

is_integer() {
    [[ "${1}" =~ ^[0-9]+$ ]]
}

json_number_or_null() {
    local value="${1}"
    if [[ "${value}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
        printf '%s' "${value}"
    else
        printf 'null'
    fi
}

json_integer_or_null() {
    local value="${1}"
    if [[ "${value}" =~ ^[0-9]+$ ]]; then
        printf '%s' "${value}"
    else
        printf 'null'
    fi
}

json_bool_or_null() {
    local value="${1,,}"
    case "${value}" in
        true|false)
            printf '%s' "${value}"
            ;;
        *)
            printf 'null'
            ;;
    esac
}

normalize_temperature_c() {
    local raw="${1}"

    if [[ "${raw}" =~ ^-?[0-9]+$ ]]; then
        awk -v raw="${raw}" 'BEGIN {
            value = raw + 0
            abs_value = value < 0 ? -value : value
            if (abs_value >= 10000) {
                value = value / 1000
            } else if (abs_value >= 100) {
                value = value / 10
            }
            printf "%.1f", value
        }'
    elif [[ "${raw}" =~ ^-?[0-9]+[.][0-9]+$ ]]; then
        printf '%s' "${raw}"
    else
        echo "unknown"
    fi
}

value_for_phase() {
    local target_phase="$1"
    local value="$2"

    if [[ "${CAPTURE_PHASE}" == "${target_phase}" ]]; then
        printf '%s' "${value}"
    else
        echo "unknown"
    fi
}

default_gpu_layers_for_backend() {
    case "${1}" in
        cpu)
            echo "${DEFAULT_CPU_GPU_LAYERS}"
            ;;
        gpu_opencl)
            echo "${DEFAULT_GPU_OPENCL_LAYERS}"
            ;;
        npu_experimental)
            echo "${DEFAULT_CPU_GPU_LAYERS}"
            ;;
        *)
            return 1
            ;;
    esac
}

derive_backend_from_gpu_layers() {
    local gpu_layers="${1}"

    if ! is_integer "${gpu_layers}"; then
        echo "cpu"
        return 0
    fi

    if (( gpu_layers > 0 )); then
        echo "gpu_opencl"
    else
        echo "cpu"
    fi
}

validate_backend() {
    case "${SERVER_BACKEND}" in
        auto|cpu|gpu_opencl|npu_experimental)
            ;;
        *)
            echo "Error: Invalid backend '${SERVER_BACKEND}'." >&2
            exit 1
            ;;
    esac
}

validate_capture_phase() {
    case "${CAPTURE_PHASE}" in
        pre_run|post_run|snapshot)
            ;;
        *)
            echo "Error: Invalid capture phase '${CAPTURE_PHASE}'." >&2
            exit 1
            ;;
    esac
}

validate_integer_field() {
    local name="$1"
    local value="$2"

    if ! is_integer "${value}"; then
        echo "Error: ${name} must be an integer, got '${value}'." >&2
        exit 1
    fi
}

parse_server_args() {
    local -n argv_ref=$1
    local i
    local token

    for ((i = 1; i < ${#argv_ref[@]}; i++)); do
        token="${argv_ref[$i]}"

        case "${token}" in
            -m)
                if (( i + 1 < ${#argv_ref[@]} )); then
                    SERVER_MODEL_PATH="${argv_ref[$((i + 1))]}"
                    ((i++))
                fi
                ;;
            -c)
                if (( i + 1 < ${#argv_ref[@]} )); then
                    SERVER_CONTEXT_LENGTH="${argv_ref[$((i + 1))]}"
                    ((i++))
                fi
                ;;
            -ngl)
                if (( i + 1 < ${#argv_ref[@]} )); then
                    SERVER_GPU_LAYERS="${argv_ref[$((i + 1))]}"
                    ((i++))
                fi
                ;;
            --port)
                if (( i + 1 < ${#argv_ref[@]} )); then
                    SERVER_PORT="${argv_ref[$((i + 1))]}"
                    ((i++))
                fi
                ;;
            --port=*)
                SERVER_PORT="${token#--port=}"
                ;;
            --host)
                if (( i + 1 < ${#argv_ref[@]} )); then
                    SERVER_HOST="${argv_ref[$((i + 1))]}"
                    ((i++))
                fi
                ;;
            --host=*)
                SERVER_HOST="${token#--host=}"
                ;;
        esac
    done
}

detect_running_server_config() {
    local proc_dir
    local cmdline_path
    local first_arg
    local arg
    local -a argv=()

    for proc_dir in /proc/[0-9]*; do
        cmdline_path="${proc_dir}/cmdline"
        [[ -r "${cmdline_path}" ]] || continue

        argv=()
        while IFS= read -r -d '' arg; do
            argv+=("${arg}")
        done < "${cmdline_path}"

        [[ ${#argv[@]} -gt 0 ]] || continue
        first_arg="${argv[0]}"

        if [[ "${first_arg}" == *"/llama-server" ]] || [[ "${first_arg}" == "llama-server" ]]; then
            parse_server_args argv
            return 0
        fi
    done

    return 1
}

# Get llama.cpp git commit hash
get_llama_commit() {
    if [[ -d "${LLAMA_CPP_DIR}/.git" ]]; then
        (cd "${LLAMA_CPP_DIR}" && git rev-parse HEAD 2>/dev/null) || echo "unknown"
    else
        echo "unknown"
    fi
}

# Get llama.cpp git commit date
get_llama_commit_date() {
    if [[ -d "${LLAMA_CPP_DIR}/.git" ]]; then
        (cd "${LLAMA_CPP_DIR}" && git log -1 --format=%cI 2>/dev/null) || echo "unknown"
    else
        echo "unknown"
    fi
}

# Check if llama.cpp has uncommitted changes
get_llama_dirty() {
    if [[ -d "${LLAMA_CPP_DIR}/.git" ]]; then
        if (cd "${LLAMA_CPP_DIR}" && git diff --quiet 2>/dev/null); then
            echo "false"
        else
            echo "true"
        fi
    else
        echo "unknown"
    fi
}

# Get battery level
get_battery_level() {
    local level
    level=$(safe_read "/sys/class/power_supply/battery/capacity")
    if [[ "${level}" != "unknown" ]]; then
        echo "${level}"
    else
        # Try alternative path
        safe_read "/sys/class/power_supply/Battery/capacity"
    fi
}

# Get battery status (Charging, Discharging, etc.)
get_battery_status() {
    local status
    status=$(safe_read "/sys/class/power_supply/battery/status")
    if [[ "${status}" != "unknown" ]]; then
        echo "${status}"
    else
        safe_read "/sys/class/power_supply/Battery/status"
    fi
}

# Get battery/device temperature snapshot in Celsius when Android exposes it.
# Android battery temperatures are commonly tenths of a degree Celsius; some
# thermal files expose millicelsius. normalize_temperature_c handles both.
get_battery_temperature_snapshot() {
    local raw
    raw=$(safe_read "/sys/class/power_supply/battery/temp")

    if [[ "${raw}" != "unknown" && -n "${raw}" ]]; then
        echo "sysfs_power_supply_battery_temp|$(normalize_temperature_c "${raw}")"
        return 0
    fi

    raw=$(safe_read "/sys/class/power_supply/Battery/temp")
    if [[ "${raw}" != "unknown" && -n "${raw}" ]]; then
        echo "sysfs_power_supply_Battery_temp|$(normalize_temperature_c "${raw}")"
        return 0
    fi

    if command -v dumpsys &>/dev/null; then
        raw=$(dumpsys battery 2>/dev/null | awk -F: '/^[[:space:]]*temperature:/ {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}' || true)
        if [[ -n "${raw}" ]]; then
            echo "dumpsys_battery_temperature|$(normalize_temperature_c "${raw}")"
            return 0
        fi
    fi

    echo "unavailable|unknown"
}

# Get thermal zone temperatures
get_thermal_zones() {
    local zones=""
    local first=1

    for zone in /sys/class/thermal/thermal_zone*; do
        if [[ -d "${zone}" ]]; then
            local name type temp
            name=$(basename "${zone}")
            type=$(safe_read "${zone}/type")
            temp=$(safe_read "${zone}/temp")

            if [[ ${first} -eq 1 ]]; then
                first=0
            else
                zones="${zones},"
            fi
            zones="${zones}{\"zone\":\"$(json_escape "${name}")\",\"type\":\"$(json_escape "${type}")\",\"temp_millicelsius\":\"$(json_escape "${temp}")\"}"
        fi
    done

    if [[ -n "${zones}" ]]; then
        echo "[${zones}]"
    else
        echo "[]"
    fi
}

# Get CPU information
get_cpu_info() {
    local model cores
    model=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
    cores=$(nproc 2>/dev/null || echo "unknown")

    # If model name not found (common on ARM), try Hardware
    if [[ "${model}" == "unknown" ]] || [[ -z "${model}" ]]; then
        model=$(grep -m1 "Hardware" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
    fi

    echo "{\"model\":\"${model}\",\"cores\":\"${cores}\"}"
}

# Get memory info
get_memory_info() {
    local total available
    total=$(grep "MemTotal" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "unknown")
    available=$(grep "MemAvailable" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "unknown")
    echo "{\"total_kb\":\"${total}\",\"available_kb\":\"${available}\"}"
}

# Get Android build info if available
get_android_info() {
    local sdk release device model

    if command -v getprop &>/dev/null; then
        sdk=$(getprop ro.build.version.sdk 2>/dev/null || echo "unknown")
        release=$(getprop ro.build.version.release 2>/dev/null || echo "unknown")
        device=$(getprop ro.product.device 2>/dev/null || echo "unknown")
        model=$(getprop ro.product.model 2>/dev/null || echo "unknown")
        echo "{\"sdk_version\":\"${sdk}\",\"release\":\"${release}\",\"device\":\"${device}\",\"model\":\"${model}\"}"
    else
        echo "{\"sdk_version\":\"unknown\",\"release\":\"unknown\",\"device\":\"unknown\",\"model\":\"unknown\"}"
    fi
}

# Get Termux version if available
get_termux_info() {
    if [[ -n "${TERMUX_VERSION:-}" ]]; then
        echo "${TERMUX_VERSION}"
    elif [[ -n "${PREFIX:-}" && -f "${PREFIX}/etc/termux-version" ]]; then
        cat "${PREFIX}/etc/termux-version" 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

# ==============================================================================
# Parse arguments and resolve server settings
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cpu)
            SERVER_BACKEND="cpu"
            shift
            ;;
        --gpu)
            SERVER_BACKEND="gpu_opencl"
            shift
            ;;
        --npu-experimental)
            SERVER_BACKEND="npu_experimental"
            shift
            ;;
        --backend)
            SERVER_BACKEND="$2"
            shift 2
            ;;
        --model)
            SERVER_MODEL_PATH="$2"
            shift 2
            ;;
        --context-length)
            SERVER_CONTEXT_LENGTH="$2"
            shift 2
            ;;
        --gpu-layers)
            SERVER_GPU_LAYERS="$2"
            shift 2
            ;;
        --port)
            SERVER_PORT="$2"
            shift 2
            ;;
        --host)
            SERVER_HOST="$2"
            shift 2
            ;;
        --phase)
            CAPTURE_PHASE="${2//-/_}"
            shift 2
            ;;
        --background-apps-minimized)
            BACKGROUND_APPS_MINIMIZED="$2"
            shift 2
            ;;
        --known-anomalies)
            KNOWN_ANOMALIES="$2"
            shift 2
            ;;
        --manual-observations)
            MANUAL_OBSERVATIONS="$2"
            shift 2
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            print_usage >&2
            exit 1
            ;;
    esac
done

validate_backend
validate_capture_phase

if detect_running_server_config; then
    if [[ "${SERVER_BACKEND}" == "auto" ]]; then
        SERVER_BACKEND="$(derive_backend_from_gpu_layers "${SERVER_GPU_LAYERS:-${DEFAULT_CPU_GPU_LAYERS}}")"
    fi
else
    warn "No running llama-server process detected; using configured/default server settings in metadata output."
fi

if [[ "${SERVER_BACKEND}" == "auto" ]]; then
    SERVER_BACKEND="cpu"
fi

if [[ -z "${SERVER_GPU_LAYERS}" ]]; then
    SERVER_GPU_LAYERS="$(default_gpu_layers_for_backend "${SERVER_BACKEND}")"
fi

validate_integer_field "SERVER_CONTEXT_LENGTH" "${SERVER_CONTEXT_LENGTH}"
validate_integer_field "SERVER_GPU_LAYERS" "${SERVER_GPU_LAYERS}"
validate_integer_field "SERVER_PORT" "${SERVER_PORT}"

# ==============================================================================
# Capture timestamp
# ==============================================================================

CAPTURE_TIMESTAMP=$(date -Iseconds)
BATTERY_LEVEL_PERCENT="$(get_battery_level)"
BATTERY_STATUS="$(get_battery_status)"
BATTERY_TEMPERATURE_SNAPSHOT="$(get_battery_temperature_snapshot)"
TEMPERATURE_SOURCE="${BATTERY_TEMPERATURE_SNAPSHOT%%|*}"
DEVICE_TEMPERATURE_C="${BATTERY_TEMPERATURE_SNAPSHOT#*|}"
START_TEMPERATURE_C="$(value_for_phase "pre_run" "${DEVICE_TEMPERATURE_C}")"
END_TEMPERATURE_C="$(value_for_phase "post_run" "${DEVICE_TEMPERATURE_C}")"
START_BATTERY_LEVEL_PERCENT="$(value_for_phase "pre_run" "${BATTERY_LEVEL_PERCENT}")"
END_BATTERY_LEVEL_PERCENT="$(value_for_phase "post_run" "${BATTERY_LEVEL_PERCENT}")"
THERMAL_ZONES_JSON="$(get_thermal_zones)"

# ==============================================================================
# Build JSON output
# ==============================================================================

# Note: Using printf for proper JSON formatting
# The thermal_zones is already valid JSON so we don't quote it

cat << EOF
{
  "schema_version": "1.1.0",
  "capture_timestamp": "$(json_escape "${CAPTURE_TIMESTAMP}")",
  "llama_cpp": {
    "directory": "$(json_escape "${LLAMA_CPP_DIR}")",
    "commit_hash": "$(json_escape "$(get_llama_commit)")",
    "commit_date": "$(json_escape "$(get_llama_commit_date)")",
    "dirty": $(get_llama_dirty)
  },
  "device": {
    "android": $(get_android_info),
    "termux_version": "$(json_escape "$(get_termux_info)")",
    "cpu": $(get_cpu_info),
    "memory": $(get_memory_info)
  },
  "environment": {
    "capture_phase": "$(json_escape "${CAPTURE_PHASE}")",
    "device_temperature_c": $(json_number_or_null "${DEVICE_TEMPERATURE_C}"),
    "start_temperature_c": $(json_number_or_null "${START_TEMPERATURE_C}"),
    "end_temperature_c": $(json_number_or_null "${END_TEMPERATURE_C}"),
    "temperature_source": "$(json_escape "${TEMPERATURE_SOURCE}")",
    "battery_level_percent": "$(json_escape "${BATTERY_LEVEL_PERCENT}")",
    "start_battery_level_percent": $(json_integer_or_null "${START_BATTERY_LEVEL_PERCENT}"),
    "end_battery_level_percent": $(json_integer_or_null "${END_BATTERY_LEVEL_PERCENT}"),
    "battery_status": "$(json_escape "${BATTERY_STATUS}")",
    "thermal_zones": ${THERMAL_ZONES_JSON}
  },
  "server_config": {
    "model_path": "$(json_escape "${SERVER_MODEL_PATH}")",
    "context_length": ${SERVER_CONTEXT_LENGTH},
    "gpu_layers": ${SERVER_GPU_LAYERS},
    "port": ${SERVER_PORT},
    "host": "$(json_escape "${SERVER_HOST}")",
    "backend": "$(json_escape "${SERVER_BACKEND}")"
  },
  "notes": {
    "background_apps_minimized": $(json_bool_or_null "${BACKGROUND_APPS_MINIMIZED}"),
    "manual_observations": "$(json_escape "${MANUAL_OBSERVATIONS}")",
    "known_anomalies": "$(json_escape "${KNOWN_ANOMALIES}")"
  }
}
EOF
