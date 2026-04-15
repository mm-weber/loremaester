"""Root conftest — defensive stub for shared.abstractions.search.

Only activates if the shared module is NOT already installed (e.g. via
pip install r2r). When r2r is installed, shared/ is bundled and this
does nothing. In environments without r2r installed, this prevents
ImportError from any residual shared.abstractions.search references.
"""

import sys
from unittest.mock import MagicMock

try:
    import shared  # noqa: F401 — test if r2r bundled it
except ImportError:
    shared_mock = MagicMock()
    sys.modules["shared"] = shared_mock
    sys.modules["shared.abstractions"] = shared_mock.abstractions
    sys.modules["shared.abstractions.search"] = shared_mock.abstractions.search
