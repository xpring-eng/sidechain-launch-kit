from __future__ import annotations

import argparse
import os

from dotenv import dotenv_values

_ENV_VARS = {
    **os.environ,
    **{key: value for key, value in dotenv_values().items() if value},
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Create config files for testing sidechains")
    )

    parser.add_argument(
        "--usd",
        "-u",
        action="store_true",
        help=("include a USD/root IOU asset for cross chain transfers"),
    )

    parser.add_argument(
        "--cfgs_dir",
        "-c",
        help=(
            "path to configuration file dir (where the output config files will be "
            "located)"
        ),
    )

    parser.add_argument(
        "--num_federators",
        "-nf",
        help=(
            "how many federators to create config files for. Must be between 1 and 8."
        ),
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

    parser.add_argument(
        "--door_seed",
        "-d",
        help=(
            "The seed of the door account to use on the main network. Only required if "
            "not connecting to standalone mode."
        ),
    )

    return parser.parse_known_args()[0]


class ConfigParams:
    def __init__(self: ConfigParams) -> None:
        args = _parse_args()

        if "RIPPLED_SIDECHAIN_CFG_DIR" in _ENV_VARS:
            self.configs_dir = _ENV_VARS["RIPPLED_SIDECHAIN_CFG_DIR"]
        if args.cfgs_dir:
            self.configs_dir = args.cfgs_dir
        # if `self.configs_dir` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "configs_dir"):
            raise Exception(
                "Missing configs directory location. Either set the env variable "
                "RIPPLED_SIDECHAIN_CFG_DIR or use the --cfgs_dir command line switch"
            )

        if "NUM_FEDERATORS" in _ENV_VARS:
            self.num_federators = int(_ENV_VARS["NUM_FEDERATORS"])
        if args.num_federators:
            self.num_federators = int(args.num_federators)
        # if `self.num_federators` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "num_federators"):
            raise Exception(
                "Missing configs directory location. Either set the env variable "
                "NUM_FEDERATORS or use the --num_federators command line switch"
            )
        if self.num_federators < 1 or self.num_federators > 8:
            raise Exception(
                "Invalid number of federators. Expected between 1 and 8 "
                f"(inclusive), received {self.num_federators}"
            )

        mainnet = None
        if "MAINNET" in _ENV_VARS:
            mainnet = _ENV_VARS["MAINNET"]
        if args.mainnet:
            mainnet = args.mainnet
        if not mainnet:
            mainnet = "standalone"
        self.mainnet_url = "127.0.0.1" if mainnet == "standalone" else mainnet
        self.standalone = mainnet == "standalone" or mainnet == "127.0.0.1"

        self.mainnet_port = None
        if not self.standalone:
            if "MAINNET_PORT" in _ENV_VARS:
                self.mainnet_port = int(_ENV_VARS["MAINNET_PORT"])
            if args.mainnet_port:
                self.mainnet_port = int(args.mainnet_port)

        self.door_seed = None
        if not self.standalone:
            if "DOOR_ACCOUNT_SEED" in _ENV_VARS:
                self.door_seed = _ENV_VARS["DOOR_ACCOUNT_SEED"]
            if args.door_seed:
                self.door_seed = args.door_seed

        self.usd = args.usd or False
