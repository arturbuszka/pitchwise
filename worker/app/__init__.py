"""Vision worker package.

Monorepo: the `vision/` module lives one directory above `worker/`. We add the repo
root to sys.path so that `import vision...` works regardless of the cwd the worker
was started from.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
