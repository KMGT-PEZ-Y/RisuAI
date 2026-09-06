"""Enable unittest discovery with ``-s tests -t .`` from the project root."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for folder in ("src", "experiments"):
    path = str(PROJECT_ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
