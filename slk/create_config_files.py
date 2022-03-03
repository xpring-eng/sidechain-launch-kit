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

from jinja2 import Environment, FileSystemLoader
from xrpl.models import XRP, IssuedCurrency

from slk.config.config_params import ConfigParams
from slk.config.helper_classes import Ports, XChainAsset
from slk.config.network import (
    ExternalNetwork,
    Network,
    SidechainNetwork,
    StandaloneNetwork,
)
from slk.utils.eprint import eprint

JINJA_ENV = Environment(loader=FileSystemLoader(searchpath="./slk/config/templates"))

NODE_SIZE = "medium"


# generate a mainchain standalone rippled.cfg file
def _generate_cfg_dir_mainchain(
    *,
    ports: Ports,
    with_shards: bool = False,
    cfg_type: str,
    validation_seed: str,
    data_dir: str,
    full_history: bool = False,
) -> str:
    sub_dir = f"{data_dir}/{cfg_type}"
    template = JINJA_ENV.get_template("mainchain_standalone.jinja")

    for path in ["", "/db", "/shards"]:
        Path(sub_dir + path).mkdir(parents=True, exist_ok=True)

    template_data = {
        "sub_dir": sub_dir,
        "full_history": full_history,
        # ports stanza
        "ports": ports.to_dict(),
        # other
        "node_size": NODE_SIZE,
        "with_shards": with_shards,
    }

    # add the rippled.cfg file
    with open(sub_dir + "/rippled.cfg", "w") as f:
        f.write(template.render(template_data))

    return sub_dir + "/rippled.cfg"


def _generate_validators_txt(sub_dir: str, validators: List[str]) -> None:
    template = JINJA_ENV.get_template("validators.jinja")

    # Add the validators.txt file
    template_data = {"validators": validators}

    with open(sub_dir + "/validators.txt", "w") as f:
        f.write(template.render(template_data))


# Generate all the rippled.cfg and validators.txt files for the sidechain nodes.
def _generate_cfg_dirs_sidechain(
    *,
    with_shards: bool = False,
    data_dir: str,
    full_history: bool = False,
    mainnet: Network,
    sidenet: SidechainNetwork,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> None:
    template = JINJA_ENV.get_template("sidechain.jinja")

    if xchain_assets is None:
        # default to xrp only at a 1:1 value
        xchain_assets = {}
        xchain_assets["xrp_xrp_sidechain_asset"] = XChainAsset(
            XRP(), XRP(), "1", "1", "400", "400"
        )

    # data that isn't node-specific
    initial_template_data = {
        "full_history": full_history,
        # sidechains-specific stanzas
        "mainchain_ip": mainnet.url,
        "mainchain_door_account": sidenet.main_account.classic_address,
        "assets": [
            {"asset_name": name, **asset.to_dict()}
            for name, asset in xchain_assets.items()
        ],
        "federators": sidenet.federator_keypairs,
        # other
        "fixed_ips": [p.to_dict() for p in sidenet.ports],
        "node_size": NODE_SIZE,
        "with_shards": with_shards,
    }

    for fed_num in range(len(sidenet.ports)):
        cfg_type = f"sidechain_{fed_num}"
        sub_dir = f"{data_dir}/{cfg_type}"

        for path in ["", "/db", "/shards"]:
            Path(sub_dir + path).mkdir(parents=True, exist_ok=True)

        validator_kp = sidenet.validator_keypairs[fed_num]
        ports = sidenet.ports[fed_num]
        validation_seed = validator_kp.secret_key
        validators = [kp.public_key for kp in sidenet.validator_keypairs]

        mainnet_i = fed_num % len(mainnet.ports)

        template_data = {
            **initial_template_data,
            "sub_dir": sub_dir,
            # ports stanza
            "ports": ports.to_dict(),
            # sidechains-specific stanzas
            "signing_key": sidenet.federator_keypairs[fed_num].secret_key,
            "mainchain_port_ws": mainnet.ports[mainnet_i].ws_public_port,
            # other
            "validation_seed": validation_seed,
        }

        # add the rippled.cfg file
        with open(sub_dir + "/rippled.cfg", "w") as f:
            f.write(template.render(template_data))

        _generate_validators_txt(sub_dir, validators)


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
            mainchain_cfg_file = _generate_cfg_dir_mainchain(
                ports=ports,
                cfg_type=f"mainchain_{i}",
                validation_seed=validator_kp.secret_key,
                data_dir=out_dir,
            )
            mainnet_cfgs.append(mainchain_cfg_file)

    _generate_cfg_dirs_sidechain(
        data_dir=out_dir,
        full_history=True,
        mainnet=mainnet,
        sidenet=sidenet,
        xchain_assets=xchain_assets,
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
    xchain_assets = {}
    xchain_assets["XRP_XRP_sidechain_asset"] = XChainAsset(
        XRP(), XRP(), "1", "1", "200", "200"
    )
    if len(params.xchain_assets) > 0:
        root = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        if params.issuer is not None:
            issuer = params.issuer.classic_address
        else:
            issuer = root
        for token in params.xchain_assets:
            main_iou_token = IssuedCurrency(currency=token, issuer=issuer)
            side_iou_token = IssuedCurrency(currency=token, issuer=root)
            xchain_assets[f"{token}_{token}_sidechain_asset"] = XChainAsset(
                main_iou_token, side_iou_token, "1", "1", "0.02", "0.02"
            )

    create_config_files(params, xchain_assets)


if __name__ == "__main__":
    main()
