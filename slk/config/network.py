"""
Classes related to networks for generating the config files.

A network is basically a representation of nodes and keypairs.
"""

from __future__ import annotations

from typing import List, Optional

from xrpl import CryptoAlgorithm
from xrpl.core.addresscodec import encode_account_public_key, encode_node_public_key
from xrpl.core.keypairs import derive_keypair, generate_seed
from xrpl.wallet import Wallet

from slk.config.helper_classes import Keypair, Ports


class Network:
    """Represents a network of validator nodes and their keypairs."""

    def __init__(self: Network, num_nodes: int, ports: List[Ports]) -> None:
        """
        Initialize a Network for config files.

        Args:
            num_nodes: The number of nodes in the network.
            ports: The Ports for the network.
        """
        self.url = "127.0.0.1"
        self.num_nodes = num_nodes
        self.ports = ports


class StandaloneNetwork(Network):
    """Represents a network that is standalone and running locally."""

    def __init__(
        self: StandaloneNetwork, start_cfg_index: int, num_nodes: int = 1
    ) -> None:
        """
        Initializes a StandaloneNetwork.

        Args:
            num_nodes: The number of nodes in the network.
            start_cfg_index: The port number the set of ports should start at.
        """
        ports = [Ports.generate(start_cfg_index + i) for i in range(num_nodes)]
        super().__init__(num_nodes, ports)
        self.validator_keypairs = self._generate_node_keypairs()

    def _generate_node_keypairs(self: StandaloneNetwork) -> List[Keypair]:
        # Generate keypairs suitable for validator keys
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


class SidechainNetwork(StandaloneNetwork):
    """Represents a sidechain network of federator nodes and their keypairs."""

    def __init__(
        self: SidechainNetwork,
        num_federators: int,
        start_cfg_index: int,
        main_door_seed: Optional[str] = None,
    ) -> None:
        """
        Initialize a SidechainNetwork for config files.

        Args:
            num_federators: The number of federators in the network.
            start_cfg_index: The port number the ports should start at.
            main_door_seed: The secret seed of the door account on the mainchain. Only
                needed if the mainchain is an external chain (e.g.
                mainnet/devnet/testnet).
        """
        super().__init__(start_cfg_index, num_federators)
        self.num_federators = num_federators
        self.federator_keypairs = self._generate_federator_keypairs()

        if main_door_seed is None:
            self.main_account = Wallet.create(CryptoAlgorithm.SECP256K1)
            print(f"Door account seed: {self.main_account.seed}")
            print("Store this in the environment variable `DOOR_ACCOUNT_SEED`")
        else:
            self.main_account = Wallet(main_door_seed, 0)

    def _generate_federator_keypairs(self: SidechainNetwork) -> List[Keypair]:
        # Generate keypairs suitable for federator keys
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
