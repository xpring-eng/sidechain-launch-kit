NODE_SIZE = "medium"
THIS_IP = "127.0.0.1"


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