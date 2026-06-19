from __future__ import annotations

import sys
from pathlib import Path


# Force tests to import the checked-out source tree ahead of any previously installed wheel.
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "tooling"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
