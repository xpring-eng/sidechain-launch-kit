import sys
from typing import Any

EPRINT_ENABLED = True


def disable_eprint() -> None:
    global EPRINT_ENABLED
    EPRINT_ENABLED = False


def enable_eprint() -> None:
    global EPRINT_ENABLED
    EPRINT_ENABLED = True


def eprint(*args: Any, **kwargs: Any) -> None:
    if not EPRINT_ENABLED:
        return
    print(*args, file=sys.stderr, flush=True, **kwargs)
