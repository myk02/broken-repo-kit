"""Test configuration for the repository itself.

The kit's own tests live in ``tests/`` and import ``kit``. The visible base
suite lives in ``base/tests/`` and imports ``minishop``. Putting ``base`` on
``sys.path`` here lets ``python -m pytest`` run both from the repository root
without an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent / "base"
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))
