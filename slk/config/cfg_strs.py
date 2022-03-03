"""Helper methods for generating the strings that make up the config files."""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

from jinja2 import Environment, FileSystemLoader
from xrpl.models import XRP, Amount
from xrpl.wallet import Wallet

from slk.config.helper_classes import Keypair, Ports, XChainAsset

NODE_SIZE = "medium"

MAINCHAIN_IP = "127.0.0.1"
THIS_IP = "127.0.0.1"

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


def _amt_to_json(amt: Amount) -> Union[str, Dict[str, Any]]:
    if isinstance(amt, str):
        return amt
    else:
        return amt.to_dict()


def _generate_asset_stanzas(assets: Optional[Dict[str, XChainAsset]] = None) -> str:
    if assets is None:
        # default to xrp only at a 1:1 value
        assets = {}
        assets["xrp_xrp_sidechain_asset"] = XChainAsset(
            XRP(), XRP(), "1", "1", "400", "400"
        )

    index_stanza = """
[sidechain_assets]"""

    asset_stanzas = []

    for name, xchainasset in assets.items():
        index_stanza += "\n" + name
        new_stanza = f"""
[{name}]
mainchain_asset={json.dumps(_amt_to_json(xchainasset.main_asset))}
sidechain_asset={json.dumps(_amt_to_json(xchainasset.side_asset))}
mainchain_refund_penalty={json.dumps(_amt_to_json(xchainasset.main_refund_penalty))}
sidechain_refund_penalty={json.dumps(_amt_to_json(xchainasset.side_refund_penalty))}"""
        asset_stanzas.append(new_stanza)

    return index_stanza + "\n" + "\n".join(asset_stanzas)


# First element of the returned tuple is the sidechain stanzas
# second element is the bootstrap stanzas
def generate_sidechain_stanza(
    mainchain_url: str,
    mainchain_ws_port: int,
    main_account: Wallet,
    federators: List[Keypair],
    signing_key: str,
    mainchain_cfg_file: Optional[str] = None,
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> Tuple[str, str]:
    """
    Generates the [sidechain] stanza in rippled.cfg and also the [sidechain] stanza in
    the sidechain_bootstrap.cfg file.

    Args:
        mainchain_url: The URL of the mainchain. If the chain is local, it is 127.0.0.1.
        mainchain_ws_port: The WS port of the mainchain that this sidechain is
            connecting to.
        main_account: The Wallet for the door account on the mainchain.
        federators: The federators in the network.
        signing_key: The signing key used for this node.
        mainchain_cfg_file: File location of the mainchain's cfg file. Only relevant
            for standalone mode. Only used in a comment.
        xchain_assets: Cross-chain asset information.

    Returns:
        The `[sidechain]` stanzas for `rippled.cfg` and `sidechain_bootstrap.cfg`.
    """
    assets_stanzas = _generate_asset_stanzas(xchain_assets)

    federators_stanza = FEDERATORS_STANZA_INIT
    federators_secrets_stanza = FEDERATORS_SECRETS_STANZA_INIT
    bootstrap_federators_stanza = BOOTSTRAP_FEDERATORS_STANZA_INIT
    cfg_file_line = ""
    if mainchain_cfg_file is not None:
        cfg_file_line = f"# mainchain config file is: {mainchain_cfg_file}"
    for fed in federators:
        federators_stanza += f"{fed.public_key}\n"
        federators_secrets_stanza += f"{fed.secret_key}\n"
        bootstrap_federators_stanza += f"{fed.public_key} {fed.account_id}\n"

    sidechain_stanzas = f"""
[sidechain]
signing_key={signing_key}
mainchain_account={main_account.classic_address}
mainchain_ip={mainchain_url}
mainchain_port_ws={mainchain_ws_port}
{cfg_file_line}

{assets_stanzas}

{federators_stanza}

{federators_secrets_stanza if mainchain_url == THIS_IP else ""}
"""
    bootstrap_stanzas = f"""
[sidechain]
mainchain_secret={main_account.seed}

{bootstrap_federators_stanza}
"""
    return (sidechain_stanzas, bootstrap_stanzas)


def get_cfg_str_mainchain(
    ports: Ports,
    full_history: bool,
    sub_dir: str,
    disable_shards: str,
) -> str:
    """
    Generates the bulk of the boilerplate in the rippled.cfg file.

    Args:
        ports: The ports that the node is using.
        full_history: Whether to store the full history of the ledger.
        sub_dir: The subdirectory of the node's config files.
        disable_shards: Whether or not to comment out the shards stuff.

    Returns:
        The bulk of `rippled.cfg`.
    """
    env = Environment(loader=FileSystemLoader(searchpath="./slk/config/templates"))
    template = env.get_template("mainchain_standalone.jinja")

    disable_delete = "#" if full_history else ""
    history_line = "full" if full_history else "256"

    data = {
        "sub_dir": sub_dir,
        "disable_delete": disable_delete,
        "history_line": history_line,
        # ports stanza
        "ports": ports.to_dict(),
        "this_ip": THIS_IP,
        # other
        "node_size": NODE_SIZE,
        "disable_shards": disable_shards,
    }
    return template.render(data)


def get_cfg_str_sidechain(
    ports: Ports,
    full_history: bool,
    sub_dir: str,
    validation_seed_stanza: str,
    disable_shards: str,
    sidechain_stanza: str,
    fixed_ips: Optional[List[Ports]],
) -> str:
    """
    Generates the bulk of the boilerplate in the rippled.cfg file.

    Args:
        ports: The ports that the node is using.
        full_history: Whether to store the full history of the ledger.
        sub_dir: The subdirectory of the node's config files.
        validation_seed_stanza: The stanza of validation seed information.
        disable_shards: Whether or not to comment out the shards stuff.
        sidechain_stanza: The [sidechain] stanza.
        fixed_ips: The IPs for the sidechain.

    Returns:
        The bulk of `rippled.cfg`.
    """
    fixed_ips_json = [p.to_dict() for p in fixed_ips] if fixed_ips else None
    env = Environment(loader=FileSystemLoader(searchpath="./slk/config/templates"))
    template = env.get_template("sidechain.jinja")

    disable_delete = "#" if full_history else ""
    history_line = "full" if full_history else "256"

    earliest_seq_line = ""
    if sidechain_stanza:
        earliest_seq_line = "earliest_seq=1"

    data = {
        "sub_dir": sub_dir,
        "disable_delete": disable_delete,
        "history_line": history_line,
        "earliest_seq_line": earliest_seq_line,
        # ports stanza
        "ports": ports.to_dict(),
        "this_ip": THIS_IP,
        # other
        "node_size": NODE_SIZE,
        "validation_seed_stanza": validation_seed_stanza,
        "disable_shards": disable_shards,
        "sidechain_stanza": sidechain_stanza,
        "fixed_ips": fixed_ips_json,
    }
    return template.render(data)
