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

import json
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from xrpl.models import IssuedCurrencyAmount
from xrpl.wallet import Wallet

from slk.chain import single_node_chain
from slk.common import eprint
from slk.config_classes import Keypair, Network, Ports, SidechainNetwork, XChainAsset
from slk.config_file import ConfigFile
from slk.config_params import ConfigParams
from slk.config_strs import get_cfg_str, get_ips_stanza

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

MAINCHAIN_IP = "127.0.0.1"

FEDERATORS_STANZA_INIT = """
# federator signing public keys
[sidechain_federators]
"""
FEDERATORS_SECRETS_STANZA_INIT = """
# federator signing secret keys (for standalone-mode testing only; Normally won't be in
# a config file)
[sidechain_federators_secrets]
"""
BOOTSTRAP_FEDERATORS_STANZA_INIT = """
# first value is federator signing public key, second is the signing pk account
[sidechain_federators]
"""


def amt_to_json(amt):
    if isinstance(amt, str):
        return amt
    else:
        return amt.to_dict()


def generate_asset_stanzas(assets: Optional[Dict[str, XChainAsset]] = None) -> str:
    if assets is None:
        # default to xrp only at a 1:1 value
        assets = {}
        assets["xrp_xrp_sidechain_asset"] = XChainAsset("0", "0", 1, 1, 400, 400)

    index_stanza = """
[sidechain_assets]"""

    asset_stanzas = []

    for name, xchainasset in assets.items():
        index_stanza += "\n" + name
        new_stanza = f"""
[{name}]
mainchain_asset={json.dumps(amt_to_json(xchainasset.main_asset))}
sidechain_asset={json.dumps(amt_to_json(xchainasset.side_asset))}
mainchain_refund_penalty={json.dumps(amt_to_json(xchainasset.main_refund_penalty))}
sidechain_refund_penalty={json.dumps(amt_to_json(xchainasset.side_refund_penalty))}"""
        asset_stanzas.append(new_stanza)

    return index_stanza + "\n" + "\n".join(asset_stanzas)


# First element of the returned tuple is the sidechain stanzas
# second element is the bootstrap stanzas
def generate_sidechain_stanza(
    mainchain_ports: Ports,
    main_account: Wallet,
    federators: List[Keypair],
    signing_key: str,
    mainchain_cfg_file: str,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> Tuple[str, str]:
    assets_stanzas = generate_asset_stanzas(xchain_assets)

    federators_stanza = FEDERATORS_STANZA_INIT
    federators_secrets_stanza = FEDERATORS_SECRETS_STANZA_INIT
    bootstrap_federators_stanza = BOOTSTRAP_FEDERATORS_STANZA_INIT
    for fed in federators:
        federators_stanza += f"{fed.public_key}\n"
        federators_secrets_stanza += f"{fed.secret_key}\n"
        bootstrap_federators_stanza += f"{fed.public_key} {fed.account_id}\n"

    sidechain_stanzas = f"""
[sidechain]
signing_key={signing_key}
mainchain_account={main_account.classic_address}
mainchain_ip={MAINCHAIN_IP}
mainchain_port_ws={mainchain_ports.ws_public_port}
# mainchain config file is: {mainchain_cfg_file}

{assets_stanzas}

{federators_stanza}

{federators_secrets_stanza}
"""
    bootstrap_stanzas = f"""
[sidechain]
mainchain_secret={main_account.seed}

{bootstrap_federators_stanza}
"""
    return (sidechain_stanzas, bootstrap_stanzas)


# cfg_type will typically be either 'dog' or 'test', but can be any string. It is only
# used to create the data directories.
def generate_cfg_dir(
    *,
    ports: Ports,
    with_shards: bool,
    main_net: bool,
    cfg_type: str,
    sidechain_stanza: str,
    sidechain_bootstrap_stanza: str,
    validation_seed: Optional[str] = None,
    validators: Optional[List[str]] = None,
    fixed_ips: Optional[List[Ports]] = None,
    data_dir: str,
    full_history: bool = False,
    with_hooks: bool = False,
) -> str:
    ips_stanza = get_ips_stanza(fixed_ips, ports.peer_port, main_net)
    disable_shards = "" if with_shards else "# "
    disable_delete = "#" if full_history else ""
    history_line = "full" if full_history else "256"
    earliest_seq_line = ""
    if sidechain_stanza:
        earliest_seq_line = "earliest_seq=1"
    hooks_line = "Hooks" if with_hooks else ""
    validation_seed_stanza = ""
    if validation_seed:
        validation_seed_stanza = f"""
[validation_seed]
{validation_seed}
        """
    shard_str = "shards" if with_shards else "no_shards"
    net_str = "main" if main_net else "test"
    if not fixed_ips:
        sub_dir = data_dir + f"/{net_str}.{shard_str}.{cfg_type}"
        if sidechain_stanza:
            sub_dir += ".sidechain"
    else:
        sub_dir = data_dir + f"/{cfg_type}"

    cfg_str = get_cfg_str(
        ports,
        history_line,
        sub_dir,
        earliest_seq_line,
        disable_delete,
        ips_stanza,
        validation_seed_stanza,
        disable_shards,
        sidechain_stanza,
        hooks_line,
    )

    # add the rippled.cfg file
    with open(sub_dir + "/rippled.cfg", "w") as f:
        f.write(cfg_str)

    validators_str = ""
    for path in ["sub_dir", "/db", "/shards"]:
        Path(sub_dir + path).mkdir(parents=True, exist_ok=True)
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


def generate_multinode_net(
    out_dir: str,
    mainnet: Network,
    sidenet: SidechainNetwork,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
):
    mainnet_cfgs = []
    for i in range(len(mainnet.ports)):
        validator_kp = mainnet.validator_keypairs[i]
        ports = mainnet.ports[i]
        mainchain_cfg_file = generate_cfg_dir(
            ports=ports,
            with_shards=False,
            main_net=True,
            cfg_type=f"mainchain_{i}",
            sidechain_stanza="",
            sidechain_bootstrap_stanza="",
            validation_seed=validator_kp.secret_key,
            data_dir=out_dir,
        )
        mainnet_cfgs.append(mainchain_cfg_file)

    for i in range(len(sidenet.ports)):
        validator_kp = sidenet.validator_keypairs[i]
        ports = sidenet.ports[i]

        mainnet_i = i % len(mainnet.ports)
        sidechain_stanza, sidechain_bootstrap_stanza = generate_sidechain_stanza(
            mainnet.ports[mainnet_i],
            sidenet.main_account,
            sidenet.federator_keypairs,
            sidenet.federator_keypairs[i].secret_key,
            mainnet_cfgs[mainnet_i],
            xchain_assets,
        )

        generate_cfg_dir(
            ports=ports,
            with_shards=False,
            main_net=True,
            cfg_type=f"sidechain_{i}",
            sidechain_stanza=sidechain_stanza,
            sidechain_bootstrap_stanza=sidechain_bootstrap_stanza,
            validation_seed=validator_kp.secret_key,
            validators=[kp.public_key for kp in sidenet.validator_keypairs],
            fixed_ips=sidenet.ports,
            data_dir=out_dir,
            full_history=True,
            with_hooks=False,
        )


def main(params: ConfigParams, xchain_assets: Optional[Dict[str, XChainAsset]] = None):
    index = 0
    nonvalidator_cfg_file_name = generate_cfg_dir(
        ports=Ports(index),
        with_shards=False,
        main_net=True,
        cfg_type="non_validator",
        sidechain_stanza="",
        sidechain_bootstrap_stanza="",
        validation_seed=None,
        data_dir=params.configs_dir,
    )
    index = index + 1

    nonvalidator_config = ConfigFile(file_name=nonvalidator_cfg_file_name)
    with single_node_chain(exe=params.exe, config=nonvalidator_config) as rip:
        mainnet = Network(num_nodes=1, num_validators=1, start_cfg_index=index, rip=rip)
        sidenet = SidechainNetwork(
            num_nodes=5,
            num_federators=5,
            num_validators=5,
            start_cfg_index=index + 1,
            rip=rip,
        )
        generate_multinode_net(
            out_dir=f"{params.configs_dir}/sidechain_testnet",
            mainnet=mainnet,
            sidenet=sidenet,
            xchain_assets=xchain_assets,
        )
        index = index + 2

        (Path(params.configs_dir) / "logs").mkdir(parents=True, exist_ok=True)

        for with_shards in [True, False]:
            for is_main_net in [True, False]:
                for cfg_type in ["dog", "test", "one", "two"]:
                    if not is_main_net and cfg_type not in ["dog", "test"]:
                        continue

                    mainnet = Network(
                        num_nodes=1, num_validators=1, start_cfg_index=index, rip=rip
                    )
                    mainchain_cfg_file = generate_cfg_dir(
                        data_dir=params.configs_dir,
                        ports=mainnet.ports[0],
                        with_shards=with_shards,
                        main_net=is_main_net,
                        cfg_type=cfg_type,
                        sidechain_stanza="",
                        sidechain_bootstrap_stanza="",
                        validation_seed=mainnet.validator_keypairs[0].secret_key,
                    )

                    sidenet = SidechainNetwork(
                        num_nodes=1,
                        num_federators=5,
                        num_validators=1,
                        start_cfg_index=index + 1,
                        rip=rip,
                    )
                    signing_key = sidenet.federator_keypairs[0].secret_key

                    (
                        sidechain_stanza,
                        sizechain_bootstrap_stanza,
                    ) = generate_sidechain_stanza(
                        mainnet.ports[0],
                        sidenet.main_account,
                        sidenet.federator_keypairs,
                        signing_key,
                        mainchain_cfg_file,
                        xchain_assets,
                    )

                    generate_cfg_dir(
                        data_dir=params.configs_dir,
                        ports=sidenet.ports[0],
                        with_shards=with_shards,
                        main_net=is_main_net,
                        cfg_type=cfg_type,
                        sidechain_stanza=sidechain_stanza,
                        sidechain_bootstrap_stanza=sizechain_bootstrap_stanza,
                        validation_seed=sidenet.validator_keypairs[0].secret_key,
                    )
                    index = index + 2


if __name__ == "__main__":
    try:
        params = ConfigParams()
    except Exception:
        eprint(traceback.format_exc())
        sys.exit(1)

    xchain_assets = None
    if params.usd:
        xchain_assets = {}
        xchain_assets["xrp_xrp_sidechain_asset"] = XChainAsset("0", "0", 1, 1, 200, 200)

        root_account = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        main_iou_asset = IssuedCurrencyAmount(
            value="0", currency="USD", issuer=root_account
        )
        side_iou_asset = IssuedCurrencyAmount(
            value="0", currency="USD", issuer=root_account
        )
        xchain_assets["iou_iou_sidechain_asset"] = XChainAsset(
            main_iou_asset, side_iou_asset, 1, 1, 0.02, 0.02
        )

    main(params, xchain_assets)