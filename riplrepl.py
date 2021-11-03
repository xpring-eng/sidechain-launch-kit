#!/usr/bin/env python3
"""Script to run an interactive shell to test sidechains."""

import sys

import slk.interactive as interactive
from slk.common import disable_eprint, eprint
from slk.sidechain import multinode_interactive_repl, standalone_interactive_repl
from slk.sidechain_params import SidechainParams


def main():
    try:
        params = SidechainParams(interactive=True)
    except Exception as e:
        eprint("ERROR: " + str(e))
        sys.exit(1)

    interactive.set_hooks_dir(params.hooks_dir)

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
