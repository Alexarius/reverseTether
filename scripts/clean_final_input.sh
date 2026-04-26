#!/usr/bin/env bash

set -e

echo "Starting final_input cleanup for legacy short_v1 dataset folders..."

find final_input/ -type d -name "*short_v1*" -exec rm -rf {} +

echo "final_input cleanup completed successfully."
