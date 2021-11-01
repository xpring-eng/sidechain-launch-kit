import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

from tabulate import tabulate
from xrpl.models import (
    AccountInfo,
    AccountLines,
    Amount,
    FederatorInfo,
    IssuedCurrency,
    IssuedCurrencyAmount,
    LedgerAccept,
    Payment,
    Request,
    Subscribe,
    is_xrp,
)
from xrpl.models.transactions.transaction import Transaction
from xrpl.utils import drops_to_xrp

import slk.testnet as testnet
from slk.common import Account
from slk.config_file import ConfigFile
from slk.node import Node


class KeyManager:
    def __init__(self):
        self._aliases = {}  # alias -> account
        self._accounts = {}  # account id -> account

    def add(self, account: Account) -> bool:
        if account.nickname:
            self._aliases[account.nickname] = account
        self._accounts[account.account_id] = account

    def is_alias(self, name: str) -> bool:
        return name in self._aliases

    def is_account(self, account: str) -> bool:
        return account in self._accounts

    def account_from_alias(self, name: str) -> Account:
        assert name in self._aliases
        return self._aliases[name]

    def known_accounts(self) -> List[Account]:
        return list(self._accounts.values())

    def get_account(self, account: str) -> Account:
        return self._accounts[account]

    def account_id_dict(self) -> Dict[str, Account]:
        return self._accounts

    def alias_or_account_id(self, id: Union[Account, str]) -> str:
        """return the alias if it exists, otherwise return the id"""
        if isinstance(id, Account):
            return id.alias_or_account_id()

        if id in self._accounts:
            return self._accounts[id].nickname
        return id

    def alias_to_account_id(self, alias: str) -> Optional[str]:
        if id in self._aliases:
            return self._aliases[id].account_id
        return None

    def to_string(self, nickname: Optional[str] = None):
        data = []
        if nickname is not None:
            if nickname in self._aliases:
                account_id = self._aliases[nickname].account_id
            else:
                account_id = "NA"
            data.append(
                {
                    "name": nickname,
                    "address": account_id,
                }
            )
        else:
            for (k, v) in self._aliases.items():
                data.append(
                    {
                        "name": k,
                        "address": v.account_id,
                    }
                )
        return tabulate(
            data,
            headers="keys",
            tablefmt="presto",
        )


class AssetAliases:
    def __init__(self):
        self._aliases = {}  # alias -> IssuedCurrency

    def add(self, asset: IssuedCurrency, name: str):
        self._aliases[name] = asset

    def is_alias(self, name: str):
        return name in self._aliases

    def asset_from_alias(self, name: str) -> IssuedCurrency:
        assert name in self._aliases
        return self._aliases[name]

    def known_aliases(self) -> List[str]:
        return list(self._aliases.keys())

    def known_assets(self) -> List[IssuedCurrency]:
        return list(self._aliases.values())

    def to_string(self, nickname: Optional[str] = None):
        data = []
        if nickname:
            if nickname in self._aliases:
                v = self._aliases[nickname]
                currency = v.currency
                issuer = v.issuer if v.issuer else ""
            else:
                currency = "NA"
                issuer = "NA"
            data.append(
                {
                    "name": nickname,
                    "currency": currency,
                    "issuer": issuer,
                }
            )
        else:
            for (k, v) in self._aliases.items():
                data.append(
                    {
                        "name": k,
                        "currency": v.currency,
                        "issuer": v.issuer if v.issuer else "",
                    }
                )
        return tabulate(
            data,
            headers="keys",
            tablefmt="presto",
        )


class Chain:
    """Representation of one chain (mainchain/sidechain)"""

    def __init__(
        self,
        *,
        standalone: bool,
        network: Optional[testnet.Network] = None,
        node: Optional[Node] = None,
    ):
        if network and node:
            raise ValueError("Cannot specify both a testnet and node in Chain")
        if not network and not node:
            raise ValueError("Must specify a testnet or a node in Chain")

        self.standalone = standalone
        self.network = network

        if node:
            self.node = node
        else:
            self.node = self.network.get_node(0)

        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()
        root_account = Account(
            nickname="root",
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            secret_key="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
        )
        self.key_manager.add(root_account)

    def shutdown(self):
        if self.network:
            self.network.shutdown()
        else:
            self.node.shutdown()

    def send_signed(self, txn: Transaction) -> dict:
        """Sign then send the given transaction"""
        if not self.key_manager.is_account(txn.account):
            raise ValueError("Cannot sign transaction without secret key")
        account_obj = self.key_manager.get_account(txn.account)
        return self.node.sign_and_submit(txn, account_obj.wallet)

    def request(self, req: Request) -> dict:
        """Send the command to the rippled server"""
        return self.node.request(req)

    def request_json(self, req: dict) -> dict:
        """Send the JSON command to the rippled server"""
        return self.node.client.request_json(req)["result"]

    def send_subscribe_command(
        self, req: Subscribe, callback: Optional[Callable[[dict], None]] = None
    ) -> dict:
        """Send the subscription command to the rippled server."""
        if not self.node.client.is_open():
            self.node.client.open()
        self.node.client.on("transaction", callback)
        return self.node.request(req)

    def get_pids(self) -> List[int]:
        if self.network:
            return self.network.get_pids()
        if pid := self.node.get_pid():
            return [pid]

    def get_running_status(self) -> List[bool]:
        if self.network:
            return self.network.get_running_status()
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self) -> dict:
        if self.network:
            return self.network.get_brief_server_info()
        else:
            ret = {}
            for (k, v) in self.node.get_brief_server_info().items():
                ret[k] = [v]
            return ret

    def servers_start(
        self,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        *,
        extra_args: Optional[List[List[str]]] = None,
    ):
        if self.network:
            return self.network.servers_start(server_indexes, extra_args=extra_args)
        else:
            raise ValueError("Cannot start stand alone server")

    def servers_stop(self, server_indexes: Optional[Union[Set[int], List[int]]] = None):
        if self.network:
            return self.network.servers_stop(server_indexes)
        else:
            raise ValueError("Cannot stop stand alone server")

    def federator_info(
        self, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ):
        # key is server index. value is federator_info result
        result_dict = {}
        if self.network:
            if not server_indexes:
                server_indexes = [
                    i
                    for i in range(self.network.num_nodes())
                    if self.network.is_running(i)
                ]
            for i in server_indexes:
                if self.network.is_running(i):
                    result_dict[i] = self.network.get_node(i).request(FederatorInfo())
        else:
            if 0 in server_indexes:
                result_dict[0] = self.node.request(FederatorInfo())
        return result_dict

    def __call__(
        self,
        to_send: Union[Transaction, Request, str],
        callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """Call `send_signed` for transactions or `request` for requests"""
        if to_send == "open":
            self.node.client.open()
            return
        if isinstance(to_send, Subscribe):
            return self.send_subscribe_command(to_send, callback)
        assert callback is None
        if isinstance(to_send, Transaction):
            return self.send_signed(to_send)
        if isinstance(to_send, Request):
            return self.request(to_send)
        if isinstance(to_send, dict):
            return self.request_json(to_send)
        raise ValueError(
            "Expected `to_send` to be either a Transaction, Command, or "
            "SubscriptionCommand"
        )

    def get_configs(self) -> List[str]:
        if self.network:
            return self.network.get_configs()
        return [self.node.config]

    def create_account(self, name: str) -> Account:
        """Create an account. Use the name as the alias."""
        if name == "root":
            return
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

    def create_accounts(
        self,
        names: List[str],
        funding_account: Union[Account, str] = "root",
        amt: Amount = str(1_000_000_000),
    ) -> List[Account]:
        """Fund the accounts with nicknames 'names' by using funding account and amt"""
        accounts = [self.create_account(n) for n in names]
        if not isinstance(funding_account, Account):
            org_funding_account = funding_account
            funding_account = self.key_manager.account_from_alias(funding_account)
        if not isinstance(funding_account, Account):
            raise ValueError(f"Could not find funding account {org_funding_account}")
        if not isinstance(amt, Amount):
            assert isinstance(amt, int)
            amt = str(amt)
        for a in accounts:
            p = Payment(
                account=funding_account.account_id, destination=a.account_id, amount=amt
            )
            self.send_signed(p)
        return accounts

    def maybe_ledger_accept(self):
        if not self.standalone:
            return
        self(LedgerAccept())

    def get_balances(
        self,
        account: Union[Account, List[Account], None] = None,
        token: Union[Amount, List[Amount]] = "0",
    ) -> List[dict]:
        """
        Return a list of dicts of account balances. If account is None, treat as a
        wildcard (use address book)
        """
        if account is None:
            account = self.key_manager.known_accounts()
        if isinstance(account, list):
            return [d for acc in account for d in self.get_balances(acc, token)]
        if isinstance(token, list):
            return [d for ass in token for d in self.get_balances(account, ass)]
        if is_xrp(token):
            try:
                account_info = self.get_account_info(account)
                needed_data = ["account", "balance"]
                account_info = {
                    "account": account_info["account"],
                    "balance": account_info["balance"],
                }
                account_info.update({"currency": "XRP", "peer": "", "limit": ""})
                return [account_info]
            except:
                # TODO: better error handling
                # Most likely the account does not exist on the ledger. Give a balance
                # of zero.
                return [
                    {
                        "account": account,
                        "balance": 0,
                        "currency": "XRP",
                        "peer": "",
                        "limit": "",
                    }
                ]
        else:
            try:
                trustlines = self.get_trust_lines(account)
                trustlines = [
                    tl
                    for tl in trustlines
                    if (tl["peer"] == token.issuer and tl["currency"] == token.currency)
                ]
                needed_data = ["account", "balance", "currency", "peer", "limit"]
                return [
                    {k: trustline[k] for k in trustline if k in needed_data}
                    for trustline in trustlines
                ]
            except:
                # TODO: better error handling
                # Most likely the account does not exist on the ledger. Return an empty
                # data frame
                return []

    def get_balance(self, account: Account, token: IssuedCurrency) -> str:
        """Get a balance from a single account in a single token"""
        try:
            result = self.get_balances(account, token)
            return result[0]["balance"]
        except:
            return "0"

    def get_account_info(self, account: Optional[Account] = None) -> Union[dict, list]:
        """
        Return a dictionary of account info. If account is None, treat as a
        wildcard (use address book)
        """
        if account is None:
            known_accounts = self.key_manager.known_accounts()
            return [self.get_account_info(acc) for acc in known_accounts]
        try:
            result = self.node.request(AccountInfo(account=account.account_id))
        except:
            # TODO: better error checking
            # Most likely the account does not exist on the ledger. Give a balance of 0.
            return {
                "account": account.account_id,
                "balance": "0",
                "flags": 0,
                "owner_count": 0,
                "previous_txn_id": "NA",
                "previous_txn_lgr_seq": -1,
                "sequence": -1,
            }
        if "account_data" not in result:
            raise ValueError("Bad result from account_info command")
        info = result["account_data"]
        for dk in ["LedgerEntryType", "index"]:
            del info[dk]
        rename_dict = {
            "Account": "account",
            "Balance": "balance",
            "Flags": "flags",
            "OwnerCount": "owner_count",
            "PreviousTxnID": "previous_txn_id",
            "PreviousTxnLgrSeq": "previous_txn_lgr_seq",
            "Sequence": "sequence",
        }
        for key in rename_dict:
            if key in info:
                new_key = rename_dict[key]
                info[new_key] = info[key]
                del info[key]
        return info

    def get_trust_lines(
        self, account: Account, peer: Optional[Account] = None
    ) -> List[dict]:
        """
        Return a list of dictionaries representing account trust lines. If peer account
        is None, treat as a wildcard.
        """
        if peer is None:
            result = self.request(AccountLines(account=account.account_id))
        else:
            result = self.request(
                AccountLines(account=account.account_id, peer=peer.account_id)
            )
        if "lines" not in result or "account" not in result:
            raise ValueError("Bad result from account_lines command")
        address = result["account"]
        account_lines = result["lines"]
        for account_line in account_lines:
            account_line["peer"] = account_line["account"]
            account_line["account"] = address
        return account_lines

    def substitute_nicknames(
        self, items: dict, cols: List[str] = ["account", "peer"]
    ) -> list:
        for c in cols:
            if c not in items:
                continue
            items[c] = self.key_manager.alias_or_account_id(items[c])
        return

    def add_to_keymanager(self, account: Account):
        self.key_manager.add(account)

    def is_alias(self, name: str) -> bool:
        return self.key_manager.is_alias(name)

    def account_from_alias(self, name: str) -> Account:
        return self.key_manager.account_from_alias(name)

    def known_accounts(self) -> List[Account]:
        return self.key_manager.known_accounts()

    def known_asset_aliases(self) -> List[str]:
        return self.asset_aliases.known_aliases()

    def known_iou_assets(self) -> List[IssuedCurrencyAmount]:
        return self.asset_aliases.known_assets()

    def is_asset_alias(self, name: str) -> bool:
        return self.asset_aliases.is_alias(name)

    def add_asset_alias(self, asset: IssuedCurrency, name: str):
        self.asset_aliases.add(asset, name)

    def asset_from_alias(self, name: str) -> IssuedCurrency:
        return self.asset_aliases.asset_from_alias(name)

    def get_node(self) -> Node:
        return self.node


def balances_data(
    chains: List[Chain],
    chain_names: List[str],
    account_ids: Optional[List[Account]] = None,
    assets: List[Amount] = None,
    in_drops: bool = False,
):
    if account_ids is None:
        account_ids = [None] * len(chains)

    if assets is None:
        # XRP and all assets in the assets alias list
        assets = [["0"] + c.known_iou_assets() for c in chains]

    result = []
    for chain, chain_name, acc, asset in zip(chains, chain_names, account_ids, assets):
        chain_result = chain.get_balances(acc, asset)
        for chain_res in chain_result:
            chain.substitute_nicknames(chain_res)
            if not in_drops and chain_res["currency"] == "XRP":
                chain_res["balance"] = drops_to_xrp(chain_res["balance"])
            else:
                chain_res["balance"] = int(chain_res["balance"])
            chain_short_name = "main" if chain_name == "mainchain" else "side"
            chain_res["account"] = chain_short_name + " " + chain_res["account"]
        result += chain_result
    return result


# Start an app with a single node
@contextmanager
def single_node_app(
    *,
    config: ConfigFile,
    command_log: Optional[str] = None,
    server_out=os.devnull,
    run_server: bool = True,
    exe: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    standalone=False,
):
    """Start a ripple server and return an app"""
    if extra_args is None:
        extra_args = []
    server_running = False
    app = None
    node = Node(config=config, command_log=command_log, exe=exe)
    try:
        if run_server:
            node.start_server(extra_args, standalone=standalone, server_out=server_out)
            server_running = True
            time.sleep(1.5)  # give process time to startup

        app = Chain(node=node, standalone=standalone)
        yield app
    finally:
        if app:
            app.shutdown()
        if run_server and server_running:
            node.stop_server()


def configs_for_testnet(config_file_prefix: str) -> List[ConfigFile]:
    p = Path(config_file_prefix)
    dir = p.parent
    file = p.name
    file_names = []
    for f in os.listdir(dir):
        cfg = os.path.join(dir, f, "rippled.cfg")
        if f.startswith(file) and os.path.exists(cfg):
            file_names.append(cfg)
    file_names.sort()
    return [ConfigFile(file_name=f) for f in file_names]


# Start an app for a network with the config files matched by
# `config_file_prefix*/rippled.cfg`
@contextmanager
def testnet_app(
    *,
    exe: str,
    configs: List[ConfigFile],
    command_logs: Optional[List[str]] = None,
    run_server: Optional[List[bool]] = None,
    extra_args: Optional[List[List[str]]] = None,
):
    """Start a ripple testnet and return an app"""
    try:
        app = None
        network = testnet.Network(
            exe,
            configs,
            command_logs=command_logs,
            run_server=run_server,
            extra_args=extra_args,
        )
        network.wait_for_validated_ledger()
        app = Chain(network=network, standalone=False)
        yield app
    finally:
        if app:
            app.shutdown()
