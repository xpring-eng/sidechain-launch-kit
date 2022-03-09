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
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader
from xrpl.models import XRP, IssuedCurrency

from slk.config.config_params import ConfigParams
from slk.config.helper_classes import Ports, XChainAsset
from slk.config.network import SidechainNetwork, StandaloneNetwork
from slk.utils.eprint import eprint

JINJA_ENV = Environment(loader=FileSystemLoader(searchpath="./slk/config/templates"))

NODE_SIZE = "medium"


def _generate_template(
    template_name: str, template_data: Dict[str, Any], filename: str
) -> None:
    template = JINJA_ENV.get_template(template_name)

    # add the rippled.cfg file
    with open(filename, "w") as f:
        f.write(template.render(template_data))


# generate a mainchain standalone rippled.cfg file
def _generate_cfg_dir_mainchain(
    *,
    ports: Ports,
    with_shards: bool = False,
    cfg_type: str,
    validation_seed: str,
    data_dir: str,
    full_history: bool = False,
) -> None:
    sub_dir = f"{data_dir}/{cfg_type}"

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
    print(ports.to_dict())

    # add the rippled.cfg file
    _generate_template(
        "mainchain_standalone.jinja",
        template_data,
        os.path.join(data_dir, cfg_type, "rippled.cfg"),
    )


def _generate_validators_txt(sub_dir: str, validators: List[str]) -> None:
    _generate_template(
        "validators.jinja", {"validators": validators}, sub_dir + "/validators.txt"
    )


# Generate all the rippled.cfg and validators.txt files for the sidechain nodes.
def _generate_cfg_dirs_sidechain(
    *,
    with_shards: bool = False,
    data_dir: str,
    full_history: bool = False,
    mainnet_url: str,
    mainnet_ws_port: int,
    sidenet: SidechainNetwork,
    xchain_assets: Dict[str, XChainAsset],
) -> None:
    # data that isn't node-specific
    initial_template_data = {
        "full_history": full_history,
        # sidechains-specific stanzas
        "mainchain_ip": mainnet_url,
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
        sub_dir = os.path.join(data_dir, cfg_type)

        for path in ["", "/db", "/shards"]:
            Path(sub_dir + path).mkdir(parents=True, exist_ok=True)

        validator_kp = sidenet.validator_keypairs[fed_num]
        ports = sidenet.ports[fed_num]
        validation_seed = validator_kp.secret_key
        validators = [kp.public_key for kp in sidenet.validator_keypairs]

        template_data = {
            **initial_template_data,
            "sub_dir": sub_dir,
            # ports stanza
            "ports": ports.to_dict(),
            # sidechains-specific stanzas
            "signing_key": sidenet.federator_keypairs[fed_num].secret_key,
            "mainchain_port_ws": mainnet_ws_port,
            # other
            "validation_seed": validation_seed,
        }
        print(ports.to_dict())

        # add the rippled.cfg file
        _generate_template(
            "sidechain.jinja", template_data, os.path.join(sub_dir, "rippled.cfg")
        )

        _generate_validators_txt(sub_dir, validators)


def create_config_files(
    params: ConfigParams, xchain_assets: Dict[str, XChainAsset]
) -> None:
    """
    Create the config files for a network.

    Args:
        params: The command-line params provided to this method.
        xchain_assets: The cross-chain assets that are allowed to cross the network
            bridge.
    """
    # Set up directory
    out_dir = f"{params.configs_dir}/sidechain_testnet"
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

    # create logs directory
    (Path(params.configs_dir) / "logs").mkdir(parents=True, exist_ok=True)

    index = 0

    if params.standalone:
        mainnet = StandaloneNetwork(start_cfg_index=index)

        # generate mainchain config files
        for i in range(len(mainnet.ports)):
            validator_kp = mainnet.validator_keypairs[i]
            ports = mainnet.ports[i]
            _generate_cfg_dir_mainchain(
                ports=ports,
                cfg_type=f"mainchain_{i}",
                validation_seed=validator_kp.secret_key,
                data_dir=out_dir,
            )

        mainnet_url = mainnet.url
        mainnet_ws_port = mainnet.ports[0].ws_public_port

        index += 1
    else:
        assert params.mainnet_port is not None  # TODO: better error handling
        mainnet_url = params.mainnet_url
        mainnet_ws_port = params.mainnet_port

    # generate sidechain config files
    sidenet = SidechainNetwork(
        num_federators=params.num_federators,
        start_cfg_index=index,
        main_door_seed=params.door_seed,
    )

    _generate_cfg_dirs_sidechain(
        data_dir=out_dir,
        full_history=True,
        mainnet_url=mainnet_url,
        mainnet_ws_port=mainnet_ws_port,
        sidenet=sidenet,
        xchain_assets=xchain_assets,
    )


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
