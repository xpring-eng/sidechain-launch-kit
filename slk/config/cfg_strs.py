"""Helper methods for generating the strings that make up the config files."""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

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


def get_ips_stanza(
    fixed_ips: Optional[List[Ports]], peer_port: int, main_net: bool
) -> str:
    """
    Generates the stanzas that contains all the information about IPs for the sidechain.

    These are [ips_fixed] and [ips].

    Args:
        fixed_ips: The ips for the sidechain network.
        peer_port: The peer port of the node whose config file this is.
        main_net: Whether this is on the mainnet (or testnet). #TODO: not sure if needed

    Returns:
        The `[ips]` and `[ips_fixed]` stanzas for `rippled.cfg`.
    """
    ips_stanza = ""
    if fixed_ips:
        ips_stanza = "# Fixed ips for a testnet.\n"
        ips_stanza += "[ips_fixed]\n"
        for i, p in enumerate(fixed_ips):
            if p.peer_port == peer_port:
                continue
            # rippled limits number of connects per ip. So use other loopback devices
            ips_stanza += f"127.0.0.{i+1} {p.peer_port}\n"
    else:
        ips_stanza = "# Where to find some other servers speaking Ripple protocol.\n"
        ips_stanza += "[ips]\n"
        if main_net:
            ips_stanza += "r.ripple.com 51235\n"
        else:
            ips_stanza += "r.altnet.rippletest.net 51235\n"
    return ips_stanza


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
        mainchain_ports: The ports of the mainchain that this sidechain is connecting
            to.
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


def get_cfg_str(
    ports: Ports,
    full_history: bool,
    sub_dir: str,
    ips_stanza: str,
    validation_seed_stanza: str,
    disable_shards: str,
    sidechain_stanza: str,
    with_hooks: bool,
) -> str:
    """
    Generates the bulk of the boilerplate in the rippled.cfg file.

    Args:
        ports: The ports that the node is using.
        full_history: Whether to store the full history of the ledger.
        sub_dir: The subdirectory of the node's config files.
        ips_stanza: The stanza of IP information (generated by get_ips_stanza above).
        validation_seed_stanza: The stanza of validation seed information.
        disable_shards: Whether or not to comment out the shards stuff.
        sidechain_stanza: The [sidechain] stanza.
        with_hooks: Whether or not to have hooks support in the chain.

    Returns:
        The bulk of `rippled.cfg`.
    """
    db_path = sub_dir + "/db"
    debug_logfile = sub_dir + "/debug.log"
    shard_db_path = sub_dir + "/shards"
    node_db_path = db_path + "/nudb"

    disable_delete = "#" if full_history else ""
    history_line = "full" if full_history else "256"

    earliest_seq_line = ""
    if sidechain_stanza:
        earliest_seq_line = "earliest_seq=1"

    return f"""
{_get_server_stanza()}

{_get_ports_stanzas(ports)}

[node_size]
{NODE_SIZE}

[ledger_history]
{history_line}

{_get_node_db_stanza(node_db_path, earliest_seq_line, disable_delete)}

[database_path]
{db_path}

# This needs to be an absolute directory reference, not a relative one.
# Modify this value as required.
[debug_logfile]
{debug_logfile}

[sntp_servers]
time.windows.com
time.apple.com
time.nist.gov
pool.ntp.org

{ips_stanza}

[validators_file]
validators.txt

[rpc_startup]
{{ "command": "log_level", "severity": "fatal" }}
{{ "command": "log_level", "partition": "SidechainFederator", "severity": "trace" }}

[ssl_verify]
1

{validation_seed_stanza}

{disable_shards}[shard_db]
{disable_shards}type=NuDB
{disable_shards}path={shard_db_path}
{disable_shards}max_historical_shards=6

{sidechain_stanza}

{_get_features_stanza(with_hooks)}
"""


def _get_server_stanza() -> str:
    return """[server]
port_rpc_admin_local
port_peer
port_ws_admin_local
port_ws_public
#ssl_key = /etc/ssl/private/server.key
#ssl_cert = /etc/ssl/certs/server.crt"""


def _get_ports_stanzas(ports: Ports) -> str:
    return f"""[port_rpc_admin_local]
port = {ports.http_admin_port}
ip = {THIS_IP}
admin = {THIS_IP}
protocol = http

[port_peer]
port = {ports.peer_port}
ip = 0.0.0.0
protocol = peer

[port_ws_admin_local]
port = {ports.ws_admin_port}
ip = {THIS_IP}
admin = {THIS_IP}
protocol = ws

[port_ws_public]
port = {ports.ws_public_port}
ip = {THIS_IP}
protocol = ws
# protocol = wss"""


def _get_node_db_stanza(
    node_db_path: str, earliest_seq_line: str, disable_delete: str
) -> str:
    return f"""[node_db]
type=NuDB
path={node_db_path}
open_files=2000
filter_bits=12
cache_mb=256
file_size_mb=8
file_size_mult=2
{earliest_seq_line}
{disable_delete}online_delete=256
{disable_delete}advisory_delete=0"""


def _get_features_stanza(with_hooks: bool) -> str:
    return f"""[features]
{"Hooks" if with_hooks else ""}
PayChan
Flow
FlowCross
TickSize
fix1368
Escrow
fix1373
EnforceInvariants
SortedDirectories
fix1201
fix1512
fix1513
fix1523
fix1528
DepositAuth
Checks
fix1571
fix1543
fix1623
DepositPreauth
fix1515
fix1578
MultiSignReserve
fixTakerDryOfferRemoval
fixMasterKeyAsRegularKey
fixCheckThreading
fixPayChanRecipientOwnerDir
DeletableAccounts
fixQualityUpperBound
RequireFullyCanonicalSig
fix1781
HardenedValidations
fixAmendmentMajorityCalc
NegativeUNL
TicketBatch
FlowSortStrands
fixSTAmountCanonicalize
fixRmSmallIncreasedQOffers
CheckCashMakesTrustLine"""
