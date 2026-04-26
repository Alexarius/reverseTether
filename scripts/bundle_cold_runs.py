#!/usr/bin/env python3
"""
Bundle fragmented cold benchmark runs into unified directories.

This script scans a base directory for folders matching a split cold run 
pattern (e.g., YYYYMMDD_HHMMSS_node_backend_cold_...) and merges their 
raw_metrics.jsonl and metadata.json files into a single, valid directory 
(YYYYMMDD_HHMMSS_node_backend_cold) that aggregate.py can ingest.
"""

import os
import re
import shutil
import argparse
from pathlib import Path

def bundle_cold_runs(base_dir: Path):
    # Regex to capture the valid base name up to the run_type
    # Example: 20260426_195648_yoga_cpu_cold_final_long_01_rep1 -> 20260426_195648_yoga_cpu_cold
    pattern = re.compile(r"^(\d{8}_\d{6}_[a-zA-Z0-9]+_[a-zA-Z0-9]+_cold)_(.+)$")
    
    groups = {}

    # Step 1: Group related directories by their base prefix
    for subdir in base_dir.iterdir():
        if not subdir.is_dir():
            continue
            
        match = pattern.match(subdir.name)
        if match:
            base_name = match.group(1)
            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(subdir)

    if not groups:
        print("No fragmented cold runs found to bundle.")
        return

    # Step 2: Merge the grouped directories
    for base_name, folders in groups.items():
        target_dir = base_dir / base_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        combined_metrics_path = target_dir / "raw_metrics.jsonl"
        target_metadata_path = target_dir / "metadata.json"
        
        print(f"Bundling {len(folders)} folders into -> {base_name}")
        
        # Open the target JSONL file in append mode
        with open(combined_metrics_path, 'w', encoding='utf-8') as outfile:
            for i, folder in enumerate(sorted(folders)):
                metrics_file = folder / "raw_metrics.jsonl"
                
                # Concatenate metrics
                if metrics_file.exists():
                    with open(metrics_file, 'r', encoding='utf-8') as infile:
                        shutil.copyfileobj(infile, outfile)
                
                # Copy the first metadata.json we find (they should be identical at the suite level)
                if i == 0:
                    meta_file = folder / "metadata.json"
                    if meta_file.exists() and not target_metadata_path.exists():
                        shutil.copy2(meta_file, target_metadata_path)
                        
        print(f"Successfully generated bundled metrics for {base_name}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Bundle fragmented cold runs.")
    parser.add_argument(
        "input_path", 
        type=Path, 
        nargs="?", 
        default=Path("."), 
        help="Path containing the run folders."
    )
    args = parser.parse_args()
    
    bundle_cold_runs(args.input_path.resolve())