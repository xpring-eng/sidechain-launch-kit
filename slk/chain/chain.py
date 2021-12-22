from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    Currency,
    GenericRequest,
    IssuedCurrency,
    Request,
    Subscribe,
    Transaction,
)

from slk.chain.asset_aliases import AssetAliases
from slk.chain.key_manager import KeyManager
from slk.chain.node import Node
from slk.classes.account import Account
from slk.classes.config_file import ConfigFile

ROOT_ACCOUNT = Account(
    nickname="root",
    account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
    seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
)


class Chain(ABC):
    """Representation of one chain (mainchain/sidechain)"""

    def __init__(self: Chain, node: Node, add_root: bool = True) -> None:
        self.node = node
        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()

        if add_root:
            self.key_manager.add(ROOT_ACCOUNT)

    @property
    @abstractmethod
    def standalone(self: Chain) -> bool:
        pass

    @abstractmethod
    def get_pids(self: Chain) -> List[int]:
        pass

    @abstractmethod
    def get_node(self: Chain, i: Optional[int] = None) -> Node:
        pass

    @abstractmethod
    def get_configs(self: Chain) -> List[ConfigFile]:
        pass

    @abstractmethod
    def get_running_status(self: Chain) -> List[bool]:
        pass

    @abstractmethod
    def shutdown(self: Chain) -> None:
        pass

    @abstractmethod
    def servers_start(
        self: Chain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        pass

    @abstractmethod
    def servers_stop(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        pass

    # rippled stuff

    def send_signed(self: Chain, txn: Transaction) -> Dict[str, Any]:
        """Sign then send the given transaction"""
        if not self.key_manager.is_account(txn.account):
            raise ValueError(f"Account {txn.account} not a known account in chain")
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

    # specific rippled methods

    def maybe_ledger_accept(self: Chain) -> None:
        if not self.standalone:
            return
        self.request(GenericRequest(command="ledger_accept"))  # type: ignore

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
            assert isinstance(token, IssuedCurrency)  # for typing
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

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    @abstractmethod
    def get_brief_server_info(self: Chain) -> Dict[str, List[Dict[str, Any]]]:
        pass

    @abstractmethod
    def federator_info(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        pass

    # Account/asset stuff

    def create_account(self: Chain, name: str) -> Account:
        """Create an account. Use the name as the alias."""
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

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
