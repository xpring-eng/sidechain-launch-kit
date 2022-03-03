#!/usr/bin/env python3

# Generate rippled config files, each with their own ports, database paths, and
# validation_seeds.
# There will be configs for shards/no_shards, main/test nets, two config files for each
# combination (so one can run in a dogfood mode while another is tested). To avoid
# confusion,The directory path will be
# $data_dir/{main | test}.{shard | no_shard}.{dog | test}
# The config file will reside in that directory with the name rippled.cfg
# The validators file will reside in that directory with the name validators.txt
"""
Script to test and debug sidechains.

The rippled exe location can be set through the command line or
the environment variable RIPPLED_MAINCHAIN_EXE

The configs_dir (where the config files will reside) can be set through the command line
or the environment variable RIPPLED_SIDECHAIN_CFG_DIR
"""
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, cast

from xrpl.models import XRP, IssuedCurrency

from slk.config.cfg_strs import generate_sidechain_stanza, get_cfg_str
from slk.config.config_params import ConfigParams
from slk.config.helper_classes import Ports, XChainAsset
from slk.config.network import (
    ExternalNetwork,
    Network,
    SidechainNetwork,
    StandaloneNetwork,
)
from slk.utils.eprint import eprint

MAINNET_VALIDATORS = """
[validator_list_sites]
https://vl.ripple.com

[validator_list_keys]
ED2677ABFFD1B33AC6FBC3062B71F1E8397C1505E1C42C64D11AD1B28FF73F4734
"""

ALTNET_VALIDATORS = """
[validator_list_sites]
https://vl.altnet.rippletest.net

[validator_list_keys]
ED264807102805220DA0F312E71FC2C69E1552C9C5790F6C25E3729DEB573D5860
"""


# Generate the rippled.cfg and validators.txt files for a rippled node.
def _generate_cfg_dir(
    *,
    ports: Ports,
    with_shards: bool = False,
    main_net: bool = True,
    cfg_type: str,
    sidechain_stanza: str = "",
    sidechain_bootstrap_stanza: str = "",
    validation_seed: str,
    validators: Optional[List[str]] = None,
    fixed_ips: Optional[List[Ports]] = None,
    data_dir: str,
    full_history: bool = False,
    with_hooks: bool = False,
) -> str:
    disable_shards = "" if with_shards else "# "
    validation_seed_stanza = f"\n[validation_seed]\n{validation_seed}\n"
    shard_str = "shards" if with_shards else "no_shards"
    net_str = "main" if main_net else "test"
    if not fixed_ips:
        sub_dir = data_dir + f"/{net_str}.{shard_str}.{cfg_type}"
        if sidechain_stanza:
            sub_dir += ".sidechain"
    else:
        sub_dir = data_dir + f"/{cfg_type}"

    for path in ["", "/db", "/shards"]:
        Path(sub_dir + path).mkdir(parents=True, exist_ok=True)

    assert ports.peer_port is not None  # TODO: better error handling/port typing

    cfg_str = get_cfg_str(
        ports,
        full_history,
        sub_dir,
        validation_seed_stanza,
        disable_shards,
        sidechain_stanza,
        with_hooks,
        fixed_ips,
    )

    # add the rippled.cfg file
    with open(sub_dir + "/rippled.cfg", "w") as f:
        f.write(cfg_str)

    validators_str = ""
    # Add the validators.txt file
    if validators:
        validators_str = "[validators]\n"
        for k in validators:
            validators_str += f"{k}\n"
    else:
        validators_str = MAINNET_VALIDATORS if main_net else ALTNET_VALIDATORS
    with open(sub_dir + "/validators.txt", "w") as f:
        f.write(validators_str)

    if sidechain_bootstrap_stanza:
        # add the bootstrap file
        with open(sub_dir + "/sidechain_bootstrap.cfg", "w") as f:
            f.write(sidechain_bootstrap_stanza)

    return sub_dir + "/rippled.cfg"


# Generate all the config files for a mainchain-sidechain setup.
def _generate_all_configs(
    out_dir: str,
    mainnet: Network,
    sidenet: SidechainNetwork,
    standalone: bool = True,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> None:
    # clear directory
    if os.path.exists(out_dir):
        for filename in os.listdir(out_dir):
            file_path = os.path.join(out_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print("Failed to delete %s. Reason: %s" % (file_path, e))

    mainnet_cfgs = []
    if standalone:
        mainnet = cast(StandaloneNetwork, mainnet)
        for i in range(len(mainnet.ports)):
            validator_kp = mainnet.validator_keypairs[i]
            ports = mainnet.ports[i]
            mainchain_cfg_file = _generate_cfg_dir(
                ports=ports,
                cfg_type=f"mainchain_{i}",
                validation_seed=validator_kp.secret_key,
                data_dir=out_dir,
            )
            mainnet_cfgs.append(mainchain_cfg_file)

    for i in range(len(sidenet.ports)):
        validator_kp = sidenet.validator_keypairs[i]
        ports = sidenet.ports[i]

        mainnet_i = i % len(mainnet.ports)
        mainnet_cfg = None
        if standalone:
            mainnet_cfg = mainnet_cfgs[mainnet_i]
        sidechain_stanza, sidechain_bootstrap_stanza = generate_sidechain_stanza(
            mainnet.url,
            mainnet.ports[mainnet_i].ws_public_port,
            sidenet.main_account,
            sidenet.federator_keypairs,
            sidenet.federator_keypairs[i].secret_key,
            mainnet_cfg,
            xchain_assets,
        )

        _generate_cfg_dir(
            ports=ports,
            cfg_type=f"sidechain_{i}",
            sidechain_stanza=sidechain_stanza,
            sidechain_bootstrap_stanza=sidechain_bootstrap_stanza,
            validation_seed=validator_kp.secret_key,
            validators=[kp.public_key for kp in sidenet.validator_keypairs],
            fixed_ips=sidenet.ports,
            data_dir=out_dir,
            full_history=True,
        )


def create_config_files(
    params: ConfigParams, xchain_assets: Optional[Dict[str, XChainAsset]] = None
) -> None:
    """
    Create the config files for a network.

    Args:
        params: The command-line params provided to this method.
        xchain_assets: The cross-chain assets that are allowed to cross the network
            bridge.
    """
    index = 0
    if params.standalone:
        mainnet: Network = StandaloneNetwork(num_nodes=1, start_cfg_index=index)
    else:
        assert params.mainnet_port is not None  # TODO: better error handling
        mainnet = ExternalNetwork(url=params.mainnet_url, ws_port=params.mainnet_port)
    sidenet = SidechainNetwork(
        num_federators=params.num_federators,
        start_cfg_index=index + 1,
        main_door_seed=params.door_seed,
    )
    _generate_all_configs(
        out_dir=f"{params.configs_dir}/sidechain_testnet",
        mainnet=mainnet,
        sidenet=sidenet,
        xchain_assets=xchain_assets,
        standalone=params.standalone,
    )
    index = index + 2

    (Path(params.configs_dir) / "logs").mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Create the config files for a network, with the given command-line params."""
    # TODO: add support for real sidechains to only generate one federator's config file
    # since real sidechain networks will have federators running on different machines
    try:
        params = ConfigParams()
    except Exception:
        eprint(traceback.format_exc())
        sys.exit(1)

    xchain_assets = None
    if params.usd:
        xchain_assets = {}
        xchain_assets["xrp_xrp_sidechain_asset"] = XChainAsset(
            XRP(), XRP(), "1", "1", "200", "200"
        )
        root = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        if params.issuer is not None:
            issuer = params.issuer.classic_address
        else:
            issuer = root
        main_iou_asset = IssuedCurrency(currency="USD", issuer=issuer)
        side_iou_asset = IssuedCurrency(currency="USD", issuer=root)
        xchain_assets["iou_iou_sidechain_asset"] = XChainAsset(
            main_iou_asset, side_iou_asset, "1", "1", "0.02", "0.02"
        )

    create_config_files(params, xchain_assets)


if __name__ == "__main__":
    main()
