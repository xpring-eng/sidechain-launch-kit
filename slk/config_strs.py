NODE_SIZE = "medium"


def get_cfg_str(
    ports,
    this_ip,
    history_line,
    node_db_path,
    earliest_seq_line,
    disable_delete,
    db_path,
    debug_logfile,
    ips_stanza,
    validation_seed_stanza,
    disable_shards,
    shard_db_path,
    sidechain_stanza,
    hooks_line,
):
    return f"""
[server]
port_rpc_admin_local
port_peer
port_ws_admin_local
port_ws_public
#ssl_key = /etc/ssl/private/server.key
#ssl_cert = /etc/ssl/certs/server.crt

[port_rpc_admin_local]
port = {ports.http_admin_port}
ip = {this_ip}
admin = {this_ip}
protocol = http

[port_peer]
port = {ports.peer_port}
ip = 0.0.0.0
protocol = peer

[port_ws_admin_local]
port = {ports.ws_admin_port}
ip = {this_ip}
admin = {this_ip}
protocol = ws

[port_ws_public]
port = {ports.ws_public_port}
ip = {this_ip}
protocol = ws
# protocol = wss

[node_size]
{NODE_SIZE}

[ledger_history]
{history_line}

[node_db]
type=NuDB
path={node_db_path}
open_files=2000
filter_bits=12
cache_mb=256
file_size_mb=8
file_size_mult=2
{earliest_seq_line}
{disable_delete}online_delete=256
{disable_delete}advisory_delete=0

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

[features]
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
CheckCashMakesTrustLine
"""
