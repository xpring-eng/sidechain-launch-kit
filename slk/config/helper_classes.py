from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from xrpl.models import Currency, IssuedCurrencyAmount


@dataclass
class Keypair:
    public_key: str
    secret_key: str
    account_id: Optional[str]


class Ports:
    """
    Port numbers for various services.
    Port numbers differ by cfg_index so different configs can run
    at the same time without interfering with each other.
    """

    peer_port_base = 51235
    http_admin_port_base = 5005
    ws_public_port_base = 6005

    def __init__(self: Ports, cfg_index: int) -> None:
        """
        Initialize a Ports.

        Args:
            cfg_index: The port number the set of ports should start at.
        """
        self.peer_port = Ports.peer_port_base + cfg_index
        self.http_admin_port = Ports.http_admin_port_base + cfg_index
        self.ws_public_port = Ports.ws_public_port_base + (2 * cfg_index)
        # note admin port uses public port base
        self.ws_admin_port = Ports.ws_public_port_base + (2 * cfg_index) + 1


class XChainAsset:
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
        Initialize an XChainAsset.

        Args:
            main_asset: Mainchain asset.
            side_asset: Sidechain asset equivalent.
            main_value: Value of the mainchain asset.
            side_value: Value of the sidechain asset.
            main_refund_penalty: ???
            side_refund_penalty: ???
        """
        self.main_asset = IssuedCurrencyAmount.from_issued_currency(
            main_asset, main_value
        )
        self.side_asset = IssuedCurrencyAmount.from_issued_currency(
            side_asset, side_value
        )
        self.main_refund_penalty = IssuedCurrencyAmount.from_issued_currency(
            main_asset, main_refund_penalty
        )
        self.side_refund_penalty = IssuedCurrencyAmount.from_issued_currency(
            side_asset, side_refund_penalty
        )
