"""Representation of one chain (e.g. mainchain/sidechain)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    Currency,
    IssuedCurrency,
    LedgerAccept,
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
    """Representation of one chain (e.g. mainchain/sidechain)."""

    def __init__(self: Chain, node: Node, add_root: bool = True) -> None:
        """
        Initializes a chain.

        Note: Do not use this __init__, only use it with the child classes.

        Args:
            node: The node to use with this chain.
            add_root: Specifies if the root account should be added to the key manager.
                The default is True.
        """
        self.node = node
        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()

        if add_root:
            self.key_manager.add(ROOT_ACCOUNT)

    @property
    @abstractmethod
    def standalone(self: Chain) -> bool:
        """Return whether the chain is in standalone mode."""
        pass

    @abstractmethod
    def get_pids(self: Chain) -> List[int]:
        """Return a list of process IDs for the nodes in the chain."""
        pass

    @abstractmethod
    def get_node(self: Chain, i: Optional[int] = None) -> Node:
        """
        Get a specific node from the chain.

        Args:
            i: The index of the node to return.

        Returns:
            The node at index i.
        """
        pass

    @abstractmethod
    def get_configs(self: Chain) -> List[ConfigFile]:
        """List all config files for the nodes in the chain."""
        pass

    @abstractmethod
    def get_running_status(self: Chain) -> List[bool]:
        """Return whether the chain is up and running."""
        pass

    @abstractmethod
    def shutdown(self: Chain) -> None:
        """Shut down the chain."""
        pass

    @abstractmethod
    def servers_start(
        self: Chain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        """
        Start the servers specified by `server_indexes` for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.
            server_out: Where to output the results.
        """
        pass

    @abstractmethod
    def servers_stop(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        """
        Stop the servers specified by `server_indexes` for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.
        """
        pass

    # rippled stuff

    def send_signed(self: Chain, txn: Transaction) -> Dict[str, Any]:
        """
        Sign and then send the given transaction.

        Args:
            txn: The transaction to sign and submit.

        Returns:
            The result of the submitted transaction.

        Raises:
            ValueError: If the transaction's account is not a known account.
        """
        if not self.key_manager.is_account(txn.account):
            raise ValueError(f"Account {txn.account} not a known account in chain.")
        account_obj = self.key_manager.get_account(txn.account)
        return self.node.sign_and_submit(txn, account_obj.wallet)

    def request(self: Chain, req: Request) -> Dict[str, Any]:
        """
        Send the request to the rippled server.

        Args:
            req: The request to send.

        Returns:
            The result of the request.
        """
        return self.node.request(req)

    def send_subscribe(
        self: Chain, req: Subscribe, callback: Callable[[Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """
        Send the subscription command to the rippled server.

        Args:
            req: The subscribe request to send.
            callback: The callback to trigger when a subscription is received.

        Returns:
            The result of the initial request.
        """
        if not self.node.client.is_open():
            self.node.client.open()
        self.node.client.on("transaction", callback)
        return self.node.request(req)

    # specific rippled methods

    def maybe_ledger_accept(self: Chain) -> None:
        """Advance the ledger if the chain is in standalone mode."""
        if not self.standalone:
            return
        self.request(LedgerAccept())

    def get_account_info(
        self: Chain, account: Optional[Account] = None
    ) -> List[Dict[str, Any]]:
        """
        Return a dictionary of account info. If account is None, use the address book
        to return information about all accounts.

        Args:
            account: The account to get information about. If None, will return
                information about all accounts in the chain. The default is None.

        Returns:
            A list of the results for the accounts.

        Raises:
            ValueError: If the account_info command fails.
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
        Get the balances for accounts in tokens.

        Args:
            account: An account or list of accounts to get balances of. If account is
                None, treat as a wildcard (use address book). The default is None.
            token: A token or list of tokens in which to get balances. If token is None,
                treat as a wildcard. The default is None.

        Returns:
            A list of dictionaries of account balances.
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
        """
        Get a balance from a single account in a single token.

        Args:
            account: The account to get the balance from.
            token: The currency to use as the balance.

        Returns:
            The balance of the token in the account.
        """
        try:
            result = self.get_balances(account, token)
            return str(result[0]["balance"])
        except:
            return "0"

    def get_trust_lines(
        self: Chain, account: Account, peer: Optional[Account] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all trustlines for the specified account.

        Args:
            account: The account to query for the trustlines.
            peer: The peer of the trustline. If None, treat as a wildcard. The default
                is None.

        Returns:
            A list of dictionaries representing account trust lines.

        Raises:
            ValueError: If the account_lines command fails.
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

    @abstractmethod
    def get_brief_server_info(self: Chain) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a dictionary of the server_state, validated_ledger_seq, and
        complete_ledgers for all the nodes in the chain.
        """
        pass

    @abstractmethod
    def federator_info(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get the federator info of the servers.

        Args:
            server_indexes: The servers to query for their federator info. If None,
                treat as a wildcard. The default is None.
        """
        pass

    # Account/asset stuff

    def create_account(self: Chain, name: str) -> Account:
        """
        Create an account for the specified alias.

        Args:
            name: The alias to use for the account.

        Returns:
            The created account.
        """
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

    def substitute_nicknames(
        self: Chain, items: Dict[str, Any], cols: List[str] = ["account", "peer"]
    ) -> None:
        """
        Substitutes in-place account IDs for nicknames.

        Args:
            items: The dictionary to use for replacements.
            cols: The columns in which to replace the account IDs. Defaults to "account"
                and "peer".
        """
        for c in cols:
            if c not in items:
                continue
            items[c] = self.key_manager.alias_or_account_id(items[c])

    def add_to_keymanager(self: Chain, account: Account) -> None:
        """
        Add an account to the bank of known accounts on the chain.

        Args:
            account: Account to add to the key manager.
        """
        self.key_manager.add(account)

    def is_alias(self: Chain, name: str) -> bool:
        """
        Determine whether an account name is known.

        Args:
            name: The alias to check.

        Returns:
            Whether the alias is a known account.
        """
        return self.key_manager.is_alias(name)

    def account_from_alias(self: Chain, name: str) -> Account:
        """
        Get an account from the account's alias.

        Args:
            name: The account's alias.

        Returns:
            The account that corresponds with the alias.
        """
        return self.key_manager.account_from_alias(name)

    def known_accounts(self: Chain) -> List[Account]:
        """
        Get a list of all known accounts on the chain.

        Returns:
            A list of all known accounts on the chain.
        """
        return self.key_manager.known_accounts()

    def known_asset_aliases(self: Chain) -> List[str]:
        """
        Get a list of all known token aliases on the chain.

        Returns:
            A list of all known token aliases on the chain.
        """
        return self.asset_aliases.known_aliases()

    def known_iou_assets(self: Chain) -> List[IssuedCurrency]:
        """
        Get a list of all known tokens on the chain.

        Returns:
            A list of all known tokens on the chain.
        """
        return self.asset_aliases.known_assets()

    def is_asset_alias(self: Chain, name: str) -> bool:
        """
        Determine whether an asset name is known.

        Args:
            name: The alias to check.

        Returns:
            Whether the alias is a known asset.
        """
        return self.asset_aliases.is_alias(name)

    def add_asset_alias(self: Chain, asset: IssuedCurrency, name: str) -> None:
        """
        Add an asset to the known assets on the chain.

        Args:
            asset: The token to add.
            name: The alias to use for the token.
        """
        self.asset_aliases.add(asset, name)

    def asset_from_alias(self: Chain, name: str) -> IssuedCurrency:
        """
        Get an asset from the asset's alias.

        Args:
            name: The asset alias.

        Returns:
            The asset tied to the alias.
        """
        return self.asset_aliases.asset_from_alias(name)
