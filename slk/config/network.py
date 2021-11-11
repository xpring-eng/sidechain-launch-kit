from __future__ import annotations

from typing import List

from xrpl import CryptoAlgorithm
from xrpl.core.addresscodec import encode_account_public_key, encode_node_public_key
from xrpl.core.keypairs import derive_keypair, generate_seed
from xrpl.wallet import Wallet

from slk.config.helper_classes import Keypair, Ports


class Network:
    def __init__(self: Network, num_nodes: int, start_cfg_index: int) -> None:
        """
        Initialize a Network for config files.

        Args:
            num_nodes: The number of nodes in the network.
            start_cfg_index: The port number the ports should start at.
        """
        self.num_nodes = num_nodes
        self.validator_keypairs = self._generate_node_keypairs()
        self.ports = [Ports(start_cfg_index + i) for i in range(self.num_nodes)]

    def _generate_node_keypairs(self: Network) -> List[Keypair]:
        """generate keypairs suitable for validator keys"""
        result = []
        for i in range(self.num_nodes):
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
        self: SidechainNetwork,
        num_federators: int,
        start_cfg_index: int,
    ) -> None:
        """
        Initialize a SidechainNetwork for config files.

        Args:
            num_federators: The number of federators in the network.
            start_cfg_index: The port number the ports should start at.
        """
        super().__init__(num_federators, start_cfg_index)
        self.num_federators = num_federators
        self.federator_keypairs = self._generate_federator_keypairs()
        self.main_account = Wallet.create(CryptoAlgorithm.SECP256K1)

    def _generate_federator_keypairs(self: SidechainNetwork) -> List[Keypair]:
        """generate keypairs suitable for federator keys"""
        result = []
        for i in range(self.num_federators):
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
