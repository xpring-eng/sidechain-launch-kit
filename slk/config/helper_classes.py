"""Helper classes for generating the config files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, Union

from xrpl.models import Amount, Currency


@dataclass
class Keypair:
    """Stores keypairs for nodes."""

    public_key: str
    secret_key: str
    account_id: Optional[str]

    def to_dict(self: Keypair) -> Dict[str, Optional[str]]:
        """
        Convert the KeyPair to a dictionary.

        Returns:
            The key info represented by the KeyPair, in dictionary form.
        """
        return {
            "public_key": self.public_key,
            "secret_key": self.secret_key,
            "account_id": self.account_id,
        }


# TODO: refactor to make this less weird between local and external
class Ports:
    """
    Port numbers for various services.
    Port numbers differ by cfg_index so different configs can run
    at the same time without interfering with each other.
    """

    peer_port_base = 51235
    http_admin_port_base = 5005
    ws_public_port_base = 6005

    def __init__(
        self: Ports,
        peer_port: Optional[int],
        http_admin_port: Optional[int],
        ws_public_port: int,
        ws_admin_port: Optional[int],
    ) -> None:
        """
        Initialize a Ports.

        Args:
            peer_port: The peer port of the node. Only needed for a local node.
            http_admin_port: The admin HTTP port of the node. Only needed for a local
                node.
            ws_public_port: The public WS port of the node.
            ws_admin_port: The admin WS port of the node. Only needed for a local node.
        """
        self.peer_port = peer_port
        self.http_admin_port = http_admin_port
        self.ws_public_port = ws_public_port
        self.ws_admin_port = ws_admin_port

    @classmethod
    def generate(cls: Type[Ports], cfg_index: int) -> Ports:
        """
        Generate a Ports with the given config index.

        Args:
            cfg_index: The port number the set of ports should start at.

        Returns:
            A Ports with the ports all set up based on the config index.
        """
        return cls(
            Ports.peer_port_base + cfg_index,
            Ports.http_admin_port_base + cfg_index,
            Ports.ws_public_port_base + (2 * cfg_index),
            # note admin port uses public port base
            Ports.ws_public_port_base + (2 * cfg_index) + 1,
        )

    def to_dict(self: Ports) -> Dict[str, Optional[int]]:
        """
        Convert the Ports to a dictionary.

        Returns:
            The ports represented by the Ports, in dictionary form.
        """
        return {
            "peer_port": self.peer_port,
            "http_admin_port": self.http_admin_port,
            "ws_public_port": self.ws_public_port,
            "ws_admin_port": self.ws_admin_port,
        }


def _amt_to_json(amt: Amount) -> Union[str, Dict[str, Any]]:
    if isinstance(amt, str):
        return amt
    else:
        return amt.to_dict()


class XChainAsset:
    """Representation of a cross-chain asset."""

    def __init__(
        self: XChainAsset,
        main_asset: Currency,
        side_asset: Currency,
        main_value: str,
        side_value: str,
        main_refund_penalty: str,
        side_refund_penalty: str,
    ) -> None:
        """
        Initialize a cross-chain asset (XChainAsset).

        Args:
            main_asset: Mainchain asset.
            side_asset: Sidechain asset equivalent.
            main_value: Value of the mainchain asset.
            side_value: Value of the sidechain asset.
            main_refund_penalty: ???
            side_refund_penalty: ???
        """
        self.main_asset = main_asset.to_amount(main_value)
        self.side_asset = side_asset.to_amount(side_value)
        self.main_refund_penalty = main_asset.to_amount(main_refund_penalty)
        self.side_refund_penalty = side_asset.to_amount(side_refund_penalty)

    def to_dict(self: XChainAsset) -> Dict[str, Any]:
        """
        Convert the XChainAsset to a dictionary.

        Returns:
            The information represented by the XChainAsset, in dictionary form.
        """
        return {
            "main_asset": json.dumps(_amt_to_json(self.main_asset)),
            "side_asset": json.dumps(_amt_to_json(self.side_asset)),
            "main_refund_penalty": json.dumps(_amt_to_json(self.main_refund_penalty)),
            "side_refund_penalty": json.dumps(_amt_to_json(self.side_refund_penalty)),
        }
