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
from xrpl.wallet import Wallet

from slk.config.cfg_strs import generate_sidechain_stanza
from slk.config.config_params import ConfigParams
from slk.config.helper_classes import Keypair, Ports, XChainAsset
from slk.config.network import (
    ExternalNetwork,
    Network,
    SidechainNetwork,
    StandaloneNetwork,
)
from slk.utils.eprint import eprint

JINJA_ENV = Environment(loader=FileSystemLoader(searchpath="./slk/config/templates"))

NODE_SIZE = "medium"


def _generate_cfg_dir_mainchain(
    *,
    ports: Ports,
    with_shards: bool = False,
    main_net: bool = True,
    cfg_type: str,
    validation_seed: str,
    data_dir: str,
    full_history: bool = False,
) -> str:
    sub_dir = f"{data_dir}/mainchain"
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


def _generate_sidechain_bootstrap(
    sub_dir: str, fed_keys: List[Keypair], mainchain_account: Wallet
) -> None:
    template = JINJA_ENV.get_template("sidechain_bootstrap.jinja")

    template_data = {
        "federators": [fed.to_dict() for fed in fed_keys],
        "mainchain_secret": mainchain_account.seed,
    }

    # add the bootstrap file
    with open(sub_dir + "/sidechain_bootstrap.cfg", "w") as f:
        f.write(template.render(template_data))


# Generate the rippled.cfg and validators.txt files for a rippled node.
def _generate_cfg_dir_sidechain(
    *,
    ports: Ports,
    with_shards: bool = False,
    main_net: bool = True,
    validation_seed: str,
    validators: List[str],
    fixed_ips: List[Ports],
    data_dir: str,
    full_history: bool = False,
    mainnet: Network,
    sidenet: SidechainNetwork,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
    fed_num: int,
) -> str:
    mainnet_i = fed_num % len(mainnet.ports)
    cfg_type = f"sidechain_{fed_num}"
    sub_dir = f"{data_dir}/{cfg_type}"
    template = JINJA_ENV.get_template("sidechain.jinja")

    for path in ["", "/db", "/shards"]:
        Path(sub_dir + path).mkdir(parents=True, exist_ok=True)

    sidechain_stanza = generate_sidechain_stanza(
        mainnet.url,
        sidenet.main_account,
        sidenet.federator_keypairs,
        xchain_assets,
    )
    if xchain_assets is None:
        # default to xrp only at a 1:1 value
        xchain_assets = {}
        xchain_assets["xrp_xrp_sidechain_asset"] = XChainAsset(
            XRP(), XRP(), "1", "1", "400", "400"
        )

    template_data = {
        "sub_dir": sub_dir,
        "full_history": full_history,
        # ports stanza
        "ports": ports.to_dict(),
        # sidechains-specific stanzas
        "signing_key": sidenet.federator_keypairs[fed_num].secret_key,
        "mainchain_door_account": sidenet.main_account.classic_address,
        "mainchain_ip": mainnet.url,
        "mainchain_port_ws": mainnet.ports[mainnet_i].ws_public_port,
        "assets": [
            {"asset_name": name, **asset.to_dict()}
            for name, asset in xchain_assets.items()
        ],
        "sidechain_stanza": sidechain_stanza,
        # other
        "fixed_ips": [p.to_dict() for p in fixed_ips],
        "node_size": NODE_SIZE,
        "validation_seed": validation_seed,
        "with_shards": with_shards,
    }

    # add the rippled.cfg file
    with open(sub_dir + "/rippled.cfg", "w") as f:
        f.write(template.render(template_data))

    _generate_validators_txt(sub_dir, validators)
    _generate_sidechain_bootstrap(
        sub_dir, sidenet.federator_keypairs, sidenet.main_account
    )

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
            mainchain_cfg_file = _generate_cfg_dir_mainchain(
                ports=ports,
                cfg_type=f"mainchain_{i}",
                validation_seed=validator_kp.secret_key,
                data_dir=out_dir,
            )
            mainnet_cfgs.append(mainchain_cfg_file)

    for i in range(len(sidenet.ports)):
        validator_kp = sidenet.validator_keypairs[i]
        ports = sidenet.ports[i]

        _generate_cfg_dir_sidechain(
            ports=ports,
            validation_seed=validator_kp.secret_key,
            validators=[kp.public_key for kp in sidenet.validator_keypairs],
            fixed_ips=sidenet.ports,
            data_dir=out_dir,
            full_history=True,
            mainnet=mainnet,
            sidenet=sidenet,
            xchain_assets=xchain_assets,
            fed_num=i,
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
