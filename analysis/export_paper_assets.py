"""Export the latest aggregation artifacts to static dissertation asset names."""

from pathlib import Path
import shutil
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results" / "summaries"
PAPER_ASSETS_DIR = REPO_ROOT / "paper" / "assets"


def get_latest_summary_dir() -> Path:
    """Return the newest summary subdirectory by filesystem timestamp."""
    if not RESULTS_DIR.exists():
        print(f"Error: summary directory does not exist: {RESULTS_DIR}")
        sys.exit(1)

    summary_dirs = [path for path in RESULTS_DIR.iterdir() if path.is_dir()]
    if not summary_dirs:
        print(f"Error: no summary directories found in {RESULTS_DIR}")
        sys.exit(1)

    return max(
        summary_dirs,
        key=lambda path: (path.stat().st_mtime, path.stat().st_ctime, path.name),
    )


def export_assets() -> None:
    """Copy files from the latest aggregation directory into paper/assets."""
    latest_summary_dir = get_latest_summary_dir()
    source_files = sorted(path for path in latest_summary_dir.iterdir() if path.is_file())

    if not source_files:
        print(f"Error: no files found in latest summary directory: {latest_summary_dir}")
        sys.exit(1)

    PAPER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    exported_files: list[str] = []
    for source_file in source_files:
        destination_file = PAPER_ASSETS_DIR / source_file.name
        shutil.copy2(source_file, destination_file)
        exported_files.append(destination_file.name)

    print(f"Exported dissertation assets from: {latest_summary_dir}")
    print(f"Destination: {PAPER_ASSETS_DIR}")
    print("Files exported:")
    for filename in exported_files:
        print(f"- {filename}")


if __name__ == "__main__":
    export_assets()
