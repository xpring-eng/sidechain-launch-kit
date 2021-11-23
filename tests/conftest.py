import pytest
from xrpl.models import XRP, IssuedCurrency

import slk.create_config_files as create_config_files
from slk.sidechain_params import _parse_args_helper

"""
Sidechains uses argparse.ArgumentParser to add command line options.
The function call to add an argument is `add_argument`. pytest uses `addoption`.
This wrapper class changes calls from `add_argument` to calls to `addoption`.
To avoid conflicts between pytest and sidechains, all sidechain arguments have
the suffix `_sc` appended to them. I.e. `--verbose` is for pytest, `--verbose_sc`
is for sidechains.
"""


class ArgumentParserWrapper:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def add_argument(self, *args, **kwargs):
        for a in args:
            if not a.startswith("--"):
                continue
            a = a + "_sc"
            self.wrapped.addoption(a, **kwargs)


def pytest_addoption(parser):
    wrapped = ArgumentParserWrapper(parser)
    _parse_args_helper(wrapped)


def _xchain_assets(ratio: int = 1):
    assets = {}
    assets["xrp_xrp_sidechain_asset"] = create_config_files.XChainAsset(
        XRP(), XRP(), "1", str(1 * ratio), "200", str(200 * ratio)
    )
    root_account = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
    main_iou_asset = IssuedCurrency(currency="USD", issuer=root_account)
    side_iou_asset = IssuedCurrency(currency="USD", issuer=root_account)
    assets["iou_iou_sidechain_asset"] = create_config_files.XChainAsset(
        main_iou_asset, side_iou_asset, "1", str(1 * ratio), "0.02", str(0.02 * ratio)
    )
    return assets


# Diction of config dirs. Key is ratio
_config_dirs = None


@pytest.fixture
def configs_dirs_dict(tmp_path):
    global _config_dirs
    if not _config_dirs:
        params = create_config_files.ConfigParams()
        _config_dirs = {}
        for ratio in (1, 2):
            params.configs_dir = str(tmp_path / f"test_config_files_{ratio}")
            create_config_files.create_config_files(params, _xchain_assets(ratio))
            _config_dirs[ratio] = params.configs_dir

    return _config_dirs
