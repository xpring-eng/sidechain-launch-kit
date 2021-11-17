from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    Currency,
    FederatorInfo,
    IssuedCurrencyAmount,
    LedgerAccept,
    Request,
    Subscribe,
)
from xrpl.models.transactions.transaction import Transaction

from slk.chain.chain_base import ChainBase
from slk.chain.node import Node
from slk.classes.account import Account
from slk.classes.config_file import ConfigFile


class Chain(ChainBase):
    """Representation of one chain (mainchain/sidechain)"""

    def __init__(
        self: Chain,
        node: Node,
    ) -> None:
        self.node = node

        super().__init__()

    @property
    def standalone(self: Chain) -> bool:
        return True

    def get_node(self: Chain, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node

    def shutdown(self: Chain) -> None:
        self.node.shutdown()

    def get_pids(self: Chain) -> List[int]:
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_running_status(self: Chain) -> List[bool]:
        if self.node.get_pid():
            return [True]
        else:
            return [False]

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

    def get_configs(self: Chain) -> List[ConfigFile]:
        return [self.node.config]

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

    def maybe_ledger_accept(self: Chain) -> None:
        if not self.standalone:
            return
        self.request(LedgerAccept())

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Chain) -> Dict[str, List[Any]]:
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        # TODO: do this more elegantly
        if server_indexes is not None and 0 in server_indexes:
            result_dict[0] = self.node.request(FederatorInfo())
        return result_dict

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
