"""Make the package importable without installing it first.

``pip install -e .`` is the normal route, but putting ``src`` on the path here
means ``python -m pytest tests/`` works in a fresh checkout too.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
