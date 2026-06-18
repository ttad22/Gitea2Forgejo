from __future__ import annotations

import sys
from pathlib import Path


TOOLING_ROOT = Path(__file__).resolve().parents[1] / "tooling"
if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))
