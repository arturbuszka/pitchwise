"""Pakiet API.

Monorepo: moduł `vision/` leży w katalogu nadrzędnym względem `api/`. Dodajemy
korzeń repo do sys.path, by `import vision...` działał niezależnie od cwd, z
którego uruchomiono uvicorn/arq.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
