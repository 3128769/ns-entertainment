"""Safety rail shared by the demo scripts."""
from __future__ import annotations

import os
import sys
from pathlib import Path

MARKER = ".ns-demo-instance"


def require_demo_dir(*, creating: bool = False) -> Path:
    raw = os.getenv("NS_DATA_DIR", "")
    path = Path(raw).resolve() if raw else None
    if path is None or str(path) in {"/", "/data"} or "ns-entertainment" in str(path):
        sys.exit("refusing to run: set NS_DATA_DIR to a scratch directory, never a real instance")
    marker = path / MARKER
    if path.exists() and any(path.iterdir()) and not marker.exists():
        sys.exit(f"refusing to run: {path} already holds data that is not a demo instance")
    if creating:
        path.mkdir(parents=True, exist_ok=True)
        marker.write_text("demo data only\n")
    elif not marker.exists():
        sys.exit("refusing to run: run `python -m dev.seed_demo` first")
    return path
