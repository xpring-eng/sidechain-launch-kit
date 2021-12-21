#!/usr/bin/env python3
"""Script to run an interactive shell to test sidechains."""

import sys
import traceback

from slk.repl import set_hooks_dir
from slk.sidechain_interaction import (
    external_node_interactive_repl,
    multinode_interactive_repl,
    standalone_interactive_repl,
)
from slk.sidechain_params import SidechainParams
from slk.utils.eprint import disable_eprint, eprint


def main() -> None:
    """Run the interactive sidechain shell, with command-line args."""
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

    if not params.main_standalone:
        external_node_interactive_repl(params)
    elif params.standalone:
        standalone_interactive_repl(params)
    else:
        multinode_interactive_repl(params)


if __name__ == "__main__":
    main()
