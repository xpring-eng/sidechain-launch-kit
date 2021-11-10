#!/usr/bin/env python3
"""Script to run an interactive shell to test sidechains."""

import sys
import traceback

from slk.common import disable_eprint, eprint
from slk.sidechain import multinode_interactive_repl, standalone_interactive_repl
from slk.sidechain_params import SidechainParams
from slk.sidechain_repl import set_hooks_dir


def main() -> None:
    try:
        params = SidechainParams(interactive=True)
    except Exception:
        eprint(traceback.format_exc())
        sys.exit(1)

    set_hooks_dir(params.hooks_dir)

    if params.verbose:
        print("eprint enabled")
    else:
        disable_eprint()

    if params.standalone:
        standalone_interactive_repl(params)
    else:
        multinode_interactive_repl(params)


if __name__ == "__main__":
    main()
