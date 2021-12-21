"""Parsing and storage of command-line args for starting a sidechain."""

from __future__ import annotations

import argparse
import os
from typing import Optional

from dotenv import dotenv_values

from slk.classes.account import Account
from slk.classes.config_file import ConfigFile

_ENV_VARS = {
    **os.environ,
    **{key: value for key, value in dotenv_values().items() if value},
}


def _parse_args_helper(parser: argparse.ArgumentParser) -> None:

    parser.add_argument(
        "--debug_sidechain",
        "-ds",
        action="store_true",
        help=("Mode to debug sidechain (prompt to run sidechain in gdb)"),
    )

    parser.add_argument(
        "--debug_mainchain",
        "-dm",
        action="store_true",
        help=("Mode to debug mainchain (prompt to run sidechain in gdb)"),
    )

    parser.add_argument(
        "--exe_mainchain",
        "-em",
        help=("path to mainchain rippled executable"),
    )

    parser.add_argument(
        "--exe_sidechain",
        "-es",
        help=("path to mainchain rippled executable"),
    )

    parser.add_argument(
        "--cfgs_dir",
        "-c",
        help=("path to configuration file dir (generated with create_config_files.py)"),
    )

    parser.add_argument(
        "--standalone",
        "-a",
        action="store_true",
        help=("run standalone tests"),
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help=("run interactive repl"),
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help=("Disable printing errors (eprint disabled)"),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help=("Enable printing errors (eprint enabled)"),
    )

    # Pauses are used for attaching debuggers and looking at logs are know checkpoints
    parser.add_argument(
        "--with_pauses",
        "-p",
        action="store_true",
        help=('Add pauses at certain checkpoints in tests until "enter" key is hit'),
    )

    parser.add_argument(
        "--hooks_dir",
        help=("path to hooks dir"),
    )

    parser.add_argument(
        "--mainnet",
        "-m",
        help=(
            "URl of the mainnet. Defaults to standalone. Type `standalone` to use a "
            "standalone node."
        ),
    )

    parser.add_argument(
        "--mainnet_port",
        "-mp",
        help=(
            "The WebSocket port for the mainnet network. Defaults to 6005. Ignored if "
            "in standalone."
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=("Test and debug sidechains"))
    _parse_args_helper(parser)
    return parser.parse_known_args()[0]


class SidechainParams:
    """A class that parses and stores command-line args for starting a sidechain."""

    def __init__(
        self: SidechainParams,
        *,
        configs_dir: Optional[str] = None,
        interactive: bool = False,
    ) -> None:
        """
        Process command-line args for spinning up a sidechain.

        Args:
            configs_dir: Pass the config folder directly in. Usually passed in via
                command args/env vars.
            interactive: Whether the REPL should be started.

        Raises:
            Exception: if the arguments provided are invalid.
        """
        args = _parse_args()

        # set up debug params
        self.debug_sidechain = False
        if args.debug_sidechain:
            self.debug_sidechain = args.debug_sidechain
        self.debug_mainchain = False
        if args.debug_mainchain:
            self.debug_mainchain = args.debug_mainchain

        # set up other params
        self.standalone = args.standalone
        self.with_pauses = args.with_pauses
        self.interactive = args.interactive or interactive
        self.quiet = args.quiet
        self.verbose = args.verbose

        if self.verbose and self.quiet:
            raise Exception(
                "Cannot specify both verbose and quiet options at the same time"
            )

        # identify network to connect to
        mainnet = None
        if "MAINNET" in _ENV_VARS:
            mainnet = _ENV_VARS["MAINNET"]
        if args.mainnet:
            mainnet = args.mainnet
        if not mainnet:
            mainnet = "standalone"
        self.mainnet_url = "127.0.0.1" if mainnet == "standalone" else mainnet
        self.main_standalone = mainnet == "standalone" or mainnet == "127.0.0.1"

        self.mainnet_port = None
        if not self.main_standalone:
            if "MAINNET_PORT" in _ENV_VARS:
                self.mainnet_port = int(_ENV_VARS["MAINNET_PORT"])
            if args.mainnet_port:
                self.mainnet_port = int(args.mainnet_port)

            if "IOU_ISSUER" in _ENV_VARS:
                self.issuer = _ENV_VARS["IOU_ISSUER"]
            # TODO: add cli arg

        if self.main_standalone:
            # identify mainchain rippled exe file location (for standalone)
            if "RIPPLED_MAINCHAIN_EXE" in _ENV_VARS:
                self.mainchain_exe = _ENV_VARS["RIPPLED_MAINCHAIN_EXE"]
            if args.exe_mainchain:
                self.mainchain_exe = args.exe_mainchain
            # if `self.mainchain_exe` doesn't exist (done this way for typing purposes)
            if not hasattr(self, "mainchain_exe"):
                raise Exception(
                    "Missing mainchain_exe location. Either set the env variable "
                    "RIPPLED_MAINCHAIN_EXE or use the --exe_mainchain command line "
                    "switch"
                )

        # identify sidechain rippled exe file location
        if "RIPPLED_SIDECHAIN_EXE" in _ENV_VARS:
            self.sidechain_exe = _ENV_VARS["RIPPLED_SIDECHAIN_EXE"]
        if args.exe_sidechain:
            self.sidechain_exe = args.exe_sidechain
        # if `self.sidechain_exe` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "sidechain_exe"):
            raise Exception(
                "Missing sidechain_exe location. Either set the env variable "
                "RIPPLED_SIDECHAIN_EXE or use the --exe_sidechain command line switch"
            )

        # identify where all the config files are located
        self.configs_dir = None
        if "RIPPLED_SIDECHAIN_CFG_DIR" in _ENV_VARS:
            self.configs_dir = _ENV_VARS["RIPPLED_SIDECHAIN_CFG_DIR"]
        if args.cfgs_dir:
            self.configs_dir = args.cfgs_dir
        if configs_dir is not None:
            self.configs_dir = configs_dir
        # if `self.configs_dir` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "configs_dir"):
            raise Exception(
                "Missing configs directory location. Either set the env variable "
                "RIPPLED_SIDECHAIN_CFG_DIR or use the --cfgs_dir command line switch"
            )

        # identify directory where hooks files are
        self.hooks_dir = None
        if "RIPPLED_SIDECHAIN_HOOKS_DIR" in _ENV_VARS:
            self.hooks_dir = _ENV_VARS["RIPPLED_SIDECHAIN_HOOKS_DIR"]
        if args.hooks_dir:
            self.hooks_dir = args.hooks_dir

        # set up config files
        self.mainchain_config = None
        if self.standalone:
            if self.main_standalone:
                self.mainchain_config = ConfigFile(
                    file_name=f"{self.configs_dir}/main.no_shards.dog/rippled.cfg"
                )
            self.sidechain_config = ConfigFile(
                file_name=f"{self.configs_dir}/main.no_shards.dog.sidechain/rippled.cfg"
            )
            self.sidechain_bootstrap_config = ConfigFile(
                file_name=f"{self.configs_dir}/main.no_shards.dog.sidechain/"
                "sidechain_bootstrap.cfg"
            )
        else:
            if self.main_standalone:
                self.mainchain_config = ConfigFile(
                    file_name=f"{self.configs_dir}/sidechain_testnet/main.no_shards."
                    "mainchain_0/rippled.cfg"
                )
            self.sidechain_config = ConfigFile(
                file_name=f"{self.configs_dir}/sidechain_testnet/sidechain_0/"
                "rippled.cfg"
            )
            self.sidechain_bootstrap_config = ConfigFile(
                file_name=f"{self.configs_dir}/sidechain_testnet/sidechain_0/"
                "sidechain_bootstrap.cfg"
            )

        # set up root/door accounts
        self.genesis_account = Account(
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
            nickname="genesis",
        )
        self.mc_door_account = Account(
            account_id=self.sidechain_config.sidechain.mainchain_account,
            seed=self.sidechain_bootstrap_config.sidechain.mainchain_secret,
            nickname="door",
        )
        self.user_account = Account(
            account_id="rJynXY96Vuq6B58pST9K5Ak5KgJ2JcRsQy",
            seed="snVsJfrr2MbVpniNiUU6EDMGBbtzN",
            nickname="alice",
        )

        self.sc_door_account = Account(
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
            nickname="door",
        )

        # set up federators
        self.federators = [
            line.split()[1].strip()
            for line in self.sidechain_bootstrap_config.sidechain_federators.get_lines()
        ]
