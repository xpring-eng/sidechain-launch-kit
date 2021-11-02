#!/usr/bin/env python3
"""Script to run an interactive shell to test sidechains."""

import sys

import slk.interactive as interactive
import slk.sidechain as sidechain
from slk.common import disable_eprint, eprint


def main():
    params = sidechain.SidechainParams()
    params.interactive = True

    interactive.set_hooks_dir(params.hooks_dir)

    if err_str := params.check_error():
        eprint(err_str)
        sys.exit(1)

    if params.verbose:
        print("eprint enabled")
    else:
        disable_eprint()

    if params.standalone:
        sidechain.standalone_interactive_repl(params)
    else:
        sidechain.multinode_interactive_repl(params)


if __name__ == "__main__":
    main()
