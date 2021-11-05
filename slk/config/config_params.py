import argparse
import os

from dotenv import load_dotenv

load_dotenv()


def _parse_args():
    parser = argparse.ArgumentParser(
        description=("Create config files for testing sidechains")
    )

    parser.add_argument(
        "--exe",
        "-e",
        help=("path to rippled executable"),
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

    return parser.parse_known_args()[0]


class ConfigParams:
    def __init__(self):
        args = _parse_args()

        if "RIPPLED_MAINCHAIN_EXE" in os.environ:
            self.exe = os.environ["RIPPLED_MAINCHAIN_EXE"]
        if args.exe:
            self.exe = args.exe
        # if `self.mainchain_exe` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "exe"):
            raise Exception(
                "Missing exe location. Either set the env variable "
                "RIPPLED_MAINCHAIN_EXE or use the --exe_mainchain command line switch"
            )

        self.configs_dir = None
        if "RIPPLED_SIDECHAIN_CFG_DIR" in os.environ:
            self.configs_dir = os.environ["RIPPLED_SIDECHAIN_CFG_DIR"]
        if args.cfgs_dir:
            self.configs_dir = args.cfgs_dir
        # if `self.configs_dir` doesn't exist (done this way for typing purposes)
        if not hasattr(self, "configs_dir"):
            raise Exception(
                "Missing configs directory location. Either set the env variable "
                "RIPPLED_SIDECHAIN_CFG_DIR or use the --cfgs_dir command line switch"
            )

        self.usd = False
        if args.usd:
            self.usd = args.usd
