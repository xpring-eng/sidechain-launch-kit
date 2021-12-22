from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Type

from xrpl.models import Currency


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

    def __init__(
        self: Ports,
        peer_port: Optional[int],
        http_admin_port: Optional[int],
        ws_public_port: int,
        ws_admin_port: Optional[int],
    ) -> None:
        self.peer_port = peer_port
        self.http_admin_port = http_admin_port
        self.ws_public_port = ws_public_port
        self.ws_admin_port = ws_admin_port

    @classmethod
    def generate(cls: Type[Ports], cfg_index: int) -> Ports:
        return cls(
            Ports.peer_port_base + cfg_index,
            Ports.http_admin_port_base + cfg_index,
            Ports.ws_public_port_base + (2 * cfg_index),
            # note admin port uses public port base
            Ports.ws_public_port_base + (2 * cfg_index) + 1,
        )


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
        self.main_asset = main_asset.to_amount(main_value)
        self.side_asset = side_asset.to_amount(side_value)
        self.main_refund_penalty = main_asset.to_amount(main_refund_penalty)
        self.side_refund_penalty = side_asset.to_amount(side_refund_penalty)
