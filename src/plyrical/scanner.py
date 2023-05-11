import sys

from pathlib import Path


def scan_dir(directory, extensions):
    files = []
    for ext in extensions:
        files.extend(Path(directory).rglob(f"*.{ext}"))

    if not files:
        print("No files found that match directory/extensions")
        sys.exit(1)
    return files
