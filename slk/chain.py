from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Union, cast

from tabulate import tabulate
from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    Currency,
    FederatorInfo,
    IssuedCurrency,
    IssuedCurrencyAmount,
    LedgerAccept,
    Request,
    Subscribe,
)
from xrpl.models.transactions.transaction import Transaction
from xrpl.utils import drops_to_xrp

from slk.common import Account
from slk.config_file import ConfigFile
from slk.node import Node


class KeyManager:
    def __init__(self: KeyManager) -> None:
        self._aliases: Dict[str, Account] = {}  # alias -> account
        self._accounts: Dict[str, Account] = {}  # account id -> account

    def add(self: KeyManager, account: Account) -> None:
        self._aliases[account.nickname] = account
        self._accounts[account.account_id] = account

    def is_alias(self: KeyManager, name: str) -> bool:
        return name in self._aliases

    def is_account(self: KeyManager, account: str) -> bool:
        return account in self._accounts

    def account_from_alias(self: KeyManager, name: str) -> Account:
        assert name in self._aliases
        return self._aliases[name]

    def known_accounts(self: KeyManager) -> List[Account]:
        return list(self._accounts.values())

    def get_account(self: KeyManager, account: str) -> Account:
        return self._accounts[account]

    def account_id_dict(self: KeyManager) -> Dict[str, Account]:
        return self._accounts

    def alias_or_account_id(self: KeyManager, account_id: Union[Account, str]) -> str:
        """return the alias if it exists, otherwise return the id"""
        if isinstance(account_id, Account):
            return account_id.nickname

        if account_id in self._accounts:
            return self._accounts[account_id].nickname
        return account_id

    def alias_to_account_id(self: KeyManager, alias: str) -> Optional[str]:
        if alias in self._aliases:
            return self._aliases[alias].account_id
        return None

    def to_string(self: KeyManager, nickname: Optional[str] = None) -> str:
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
    def __init__(self: AssetAliases) -> None:
        self._aliases: Dict[str, IssuedCurrency] = {}  # alias -> IssuedCurrency

    def add(self: AssetAliases, asset: IssuedCurrency, name: str) -> None:
        self._aliases[name] = asset

    def is_alias(self: AssetAliases, name: str) -> bool:
        return name in self._aliases

    def asset_from_alias(self: AssetAliases, name: str) -> IssuedCurrency:
        assert name in self._aliases
        return self._aliases[name]

    def known_aliases(self: AssetAliases) -> List[str]:
        return list(self._aliases.keys())

    def known_assets(self: AssetAliases) -> List[IssuedCurrency]:
        return list(self._aliases.values())

    def to_string(self: AssetAliases, nickname: Optional[str] = None) -> str:
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
        self: Chain,
        node: Node,
    ):
        self.node = node

        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()

        root_account = Account(
            nickname="root",
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
        )
        self.key_manager.add(root_account)

    @property
    def standalone(self: Chain) -> bool:
        return True

    def shutdown(self: Chain) -> None:
        self.node.shutdown()

    def send_signed(self: Chain, txn: Transaction) -> Dict[str, Any]:
        """Sign then send the given transaction"""
        if not self.key_manager.is_account(txn.account):
            raise ValueError("Cannot sign transaction without secret key")
        account_obj = self.key_manager.get_account(txn.account)
        return self.node.sign_and_submit(txn, account_obj.wallet)

    def request(self: Chain, req: Request) -> Dict[str, Any]:
        """Send the command to the rippled server"""
        return self.node.request(req)

    def send_subscribe(
        self: Chain, req: Subscribe, callback: Callable[[Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """Send the subscription command to the rippled server."""
        if not self.node.client.is_open():
            self.node.client.open()
        self.node.client.on("transaction", callback)
        return self.node.request(req)

    def get_pids(self: Chain) -> List[int]:
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_running_status(self: Chain) -> List[bool]:
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Chain) -> Dict[str, List[Any]]:
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def servers_start(
        self: Chain,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        *,
        extra_args: Optional[List[List[str]]] = None,
    ) -> None:
        raise ValueError("Cannot start stand alone server")

    def servers_stop(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        raise ValueError("Cannot stop stand alone server")

    def federator_info(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        # TODO: do this more elegantly
        if server_indexes is not None and 0 in server_indexes:
            result_dict[0] = self.node.request(FederatorInfo())
        return result_dict

    def get_configs(self: Chain) -> List[ConfigFile]:
        return [self.node.config]

    def create_account(self: Chain, name: str) -> Account:
        """Create an account. Use the name as the alias."""
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

    def maybe_ledger_accept(self: Chain) -> None:
        if not self.standalone:
            return
        self.request(LedgerAccept())

    def get_balances(
        self: Chain,
        account: Union[Account, List[Account], None] = None,
        token: Union[Currency, List[Currency]] = XRP(),
    ) -> List[Dict[str, Any]]:
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
        if isinstance(token, XRP):
            try:
                account_info = self.get_account_info(account)[0]
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
            assert isinstance(token, IssuedCurrencyAmount)  # for typing
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

    def get_balance(self: Chain, account: Account, token: Currency) -> str:
        """Get a balance from a single account in a single token"""
        try:
            result = self.get_balances(account, token)
            return cast(str, result[0]["balance"])
        except:
            return "0"

    def get_account_info(
        self: Chain, account: Optional[Account] = None
    ) -> List[Dict[str, Any]]:
        """
        Return a dictionary of account info. If account is None, treat as a
        wildcard (use address book)
        """
        if account is None:
            known_accounts = self.key_manager.known_accounts()
            return [d for acc in known_accounts for d in self.get_account_info(acc)]
        try:
            result = self.request(AccountInfo(account=account.account_id))
        except:
            # TODO: better error checking
            # Most likely the account does not exist on the ledger. Give a balance of 0.
            return [
                {
                    "account": account.account_id,
                    "balance": "0",
                    "flags": 0,
                    "owner_count": 0,
                    "previous_txn_id": "NA",
                    "previous_txn_lgr_seq": -1,
                    "sequence": -1,
                }
            ]
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
        return [cast(Dict[str, Any], info)]

    def get_trust_lines(
        self: Chain, account: Account, peer: Optional[Account] = None
    ) -> List[Dict[str, Any]]:
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
        return cast(List[Dict[str, Any]], account_lines)

    def substitute_nicknames(
        self: Chain, items: Dict[str, Any], cols: List[str] = ["account", "peer"]
    ) -> None:
        """Substitutes in-place account IDs for nicknames"""
        for c in cols:
            if c not in items:
                continue
            items[c] = self.key_manager.alias_or_account_id(items[c])

    def add_to_keymanager(self: Chain, account: Account) -> None:
        self.key_manager.add(account)

    def is_alias(self: Chain, name: str) -> bool:
        return self.key_manager.is_alias(name)

    def account_from_alias(self: Chain, name: str) -> Account:
        return self.key_manager.account_from_alias(name)

    def known_accounts(self: Chain) -> List[Account]:
        return self.key_manager.known_accounts()

    def known_asset_aliases(self: Chain) -> List[str]:
        return self.asset_aliases.known_aliases()

    def known_iou_assets(self: Chain) -> List[IssuedCurrency]:
        return self.asset_aliases.known_assets()

    def is_asset_alias(self: Chain, name: str) -> bool:
        return self.asset_aliases.is_alias(name)

    def add_asset_alias(self: Chain, asset: IssuedCurrency, name: str) -> None:
        self.asset_aliases.add(asset, name)

    def asset_from_alias(self: Chain, name: str) -> IssuedCurrency:
        return self.asset_aliases.asset_from_alias(name)

    def get_node(self: Chain, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node


def balances_data(
    chains: List[Chain],
    chain_names: List[str],
    account_ids: Optional[List[Optional[Account]]] = None,
    assets: Optional[List[List[Currency]]] = None,
    in_drops: bool = False,
) -> List[Dict[str, Any]]:
    if account_ids is None:
        account_ids = [None] * len(chains)

    if assets is None:
        # XRP and all assets in the assets alias list
        assets = [
            [cast(Currency, XRP())] + cast(List[Currency], c.known_iou_assets())
            for c in chains
        ]

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


# Start a chain with a single node
@contextmanager
def single_node_chain(
    *,
    config: ConfigFile,
    command_log: Optional[str] = None,
    server_out: str = os.devnull,
    run_server: bool = True,
    exe: str,
    extra_args: Optional[List[str]] = None,
) -> Generator[Chain, None, None]:
    """Start a ripple server and return a chain"""
    if extra_args is None:
        extra_args = []
    server_running = False
    chain = None
    node = Node(config=config, command_log=command_log, exe=exe, name="mainchain")
    try:
        if run_server:
            node.start_server(extra_args, standalone=True, server_out=server_out)
            server_running = True
            time.sleep(1.5)  # give process time to startup

        chain = Chain(node=node)
        yield chain
    finally:
        if chain:
            chain.shutdown()
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
