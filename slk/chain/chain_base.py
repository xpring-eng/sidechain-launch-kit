from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import IssuedCurrency

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


class ChainBase:
    """Representation of one chain (mainchain/sidechain)"""

    def __init__(
        self: ChainBase,
        node: Node,
    ) -> None:
        self.node = node

        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()

        self.key_manager.add(ROOT_ACCOUNT)

    @property
    def standalone(self: ChainBase) -> bool:
        return True

    def shutdown(self: ChainBase) -> None:
        self.node.shutdown()

    def get_pids(self: ChainBase) -> List[int]:
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_running_status(self: ChainBase) -> List[bool]:
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    def servers_start(
        self: ChainBase,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        *,
        extra_args: Optional[List[List[str]]] = None,
    ) -> None:
        raise ValueError("Cannot start stand alone server")

    def servers_stop(
        self: ChainBase, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        raise ValueError("Cannot stop stand alone server")

    def get_configs(self: ChainBase) -> List[ConfigFile]:
        return [self.node.config]

    def create_account(self: ChainBase, name: str) -> Account:
        """Create an account. Use the name as the alias."""
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

    def substitute_nicknames(
        self: ChainBase, items: Dict[str, Any], cols: List[str] = ["account", "peer"]
    ) -> None:
        """Substitutes in-place account IDs for nicknames"""
        for c in cols:
            if c not in items:
                continue
            items[c] = self.key_manager.alias_or_account_id(items[c])

    def add_to_keymanager(self: ChainBase, account: Account) -> None:
        self.key_manager.add(account)

    def is_alias(self: ChainBase, name: str) -> bool:
        return self.key_manager.is_alias(name)

    def account_from_alias(self: ChainBase, name: str) -> Account:
        return self.key_manager.account_from_alias(name)

    def known_accounts(self: ChainBase) -> List[Account]:
        return self.key_manager.known_accounts()

    def known_asset_aliases(self: ChainBase) -> List[str]:
        return self.asset_aliases.known_aliases()

    def known_iou_assets(self: ChainBase) -> List[IssuedCurrency]:
        return self.asset_aliases.known_assets()

    def is_asset_alias(self: ChainBase, name: str) -> bool:
        return self.asset_aliases.is_alias(name)

    def add_asset_alias(self: ChainBase, asset: IssuedCurrency, name: str) -> None:
        self.asset_aliases.add(asset, name)

    def asset_from_alias(self: ChainBase, name: str) -> IssuedCurrency:
        return self.asset_aliases.asset_from_alias(name)

    def get_node(self: ChainBase, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node
