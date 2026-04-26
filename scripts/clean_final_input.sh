#!/usr/bin/env bash

set -e

echo "Starting final_input cleanup for legacy and previous run folders..."

find final_input/ -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +

echo "final_input cleanup completed successfully."
