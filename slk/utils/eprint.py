"""Printing debugging info."""

import sys
from typing import Any

EPRINT_ENABLED = True


def disable_eprint() -> None:
    """Disable logging."""
    global EPRINT_ENABLED
    EPRINT_ENABLED = False


def enable_eprint() -> None:
    """Enable logging."""
    global EPRINT_ENABLED
    EPRINT_ENABLED = True


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print a logging statement if logging is enabled."""
    if not EPRINT_ENABLED:
        return
    print(*args, file=sys.stderr, flush=True, **kwargs)
