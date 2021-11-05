from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union

from xrpl import CryptoAlgorithm
from xrpl.core.addresscodec import encode_account_public_key, encode_node_public_key
from xrpl.core.keypairs import derive_keypair, generate_seed
from xrpl.models import Amount
from xrpl.wallet import Wallet

from slk.common import same_amount_new_value


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

    def __init__(self, cfg_index: int):
        self.peer_port = Ports.peer_port_base + cfg_index
        self.http_admin_port = Ports.http_admin_port_base + cfg_index
        self.ws_public_port = Ports.ws_public_port_base + (2 * cfg_index)
        # note admin port uses public port base
        self.ws_admin_port = Ports.ws_public_port_base + (2 * cfg_index) + 1


class Network:
    def __init__(self, num_nodes: int, num_validators: int, start_cfg_index: int):
        self.num_validators = num_validators
        self.validator_keypairs = self._generate_node_keypairs()
        self.ports = [Ports(start_cfg_index + i) for i in range(num_nodes)]

    def _generate_node_keypairs(self: Network) -> List[Keypair]:
        """generate keypairs suitable for validator keys"""
        result = []
        for i in range(self.num_validators):
            seed = generate_seed(None, CryptoAlgorithm.SECP256K1)
            pub_key, priv_key = derive_keypair(seed, True)
            result.append(
                Keypair(
                    public_key=encode_node_public_key(bytes.fromhex(pub_key)),
                    secret_key=seed,
                    account_id=None,
                )
            )
        return result


class SidechainNetwork(Network):
    def __init__(
        self,
        num_nodes: int,
        num_federators: int,
        num_validators: int,
        start_cfg_index: int,
    ):
        super().__init__(num_nodes, num_validators, start_cfg_index)
        self.num_federators = num_federators
        self.federator_keypairs = self._generate_federator_keypairs()
        self.main_account = Wallet.create(CryptoAlgorithm.SECP256K1)

    def _generate_federator_keypairs(self: SidechainNetwork) -> List[Keypair]:
        """generate keypairs suitable for federator keys"""
        result = []
        for i in range(self.num_federators):
            # TODO: clean this up after the PR gets merged in the C++ code
            wallet = Wallet.create(crypto_algorithm=CryptoAlgorithm.ED25519)
            result.append(
                Keypair(
                    public_key=encode_account_public_key(
                        bytes.fromhex(wallet.public_key)
                    ),
                    secret_key=wallet.seed,
                    account_id=wallet.classic_address,
                )
            )
        return result


class XChainAsset:
    def __init__(
        self,
        main_asset: Amount,
        side_asset: Amount,
        main_value: Union[int, float],
        side_value: Union[int, float],
        main_refund_penalty: Union[int, float],
        side_refund_penalty: Union[int, float],
    ):
        self.main_asset = same_amount_new_value(main_asset, main_value)
        self.side_asset = same_amount_new_value(side_asset, side_value)
        self.main_refund_penalty = same_amount_new_value(
            main_asset, main_refund_penalty
        )
        self.side_refund_penalty = same_amount_new_value(
            side_asset, side_refund_penalty
        )
