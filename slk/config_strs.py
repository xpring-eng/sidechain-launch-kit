import json
from typing import Dict, List, Optional, Tuple

from xrpl.wallet import Wallet

from slk.config_classes import Keypair, Ports, XChainAsset

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


def get_ips_stanza(fixed_ips, peer_port, main_net):
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


def get_cfg_str(
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
):
    db_path = sub_dir + "/db"
    debug_logfile = sub_dir + "/debug.log"
    shard_db_path = sub_dir + "/shards"
    node_db_path = db_path + "/nudb"

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

{_get_features_stanza(hooks_line)}
"""


def _get_server_stanza():
    return """[server]
port_rpc_admin_local
port_peer
port_ws_admin_local
port_ws_public
#ssl_key = /etc/ssl/private/server.key
#ssl_cert = /etc/ssl/certs/server.crt"""


def _get_ports_stanzas(ports):
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


def _get_node_db_stanza(node_db_path, earliest_seq_line, disable_delete):
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


def _get_features_stanza(hooks_line):
    return f"""[features]
{hooks_line}
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
