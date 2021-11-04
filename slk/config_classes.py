from dataclasses import dataclass
from typing import List, Optional, Union

from xrpl import CryptoAlgorithm
from xrpl.core.addresscodec import decode_seed, encode_account_public_key
from xrpl.core.addresscodec.codec import _FAMILY_SEED_PREFIX, SEED_LENGTH, _encode
from xrpl.models import Amount
from xrpl.wallet import Wallet

from slk.chain import Chain
from slk.common import same_amount_new_value


@dataclass
class Keypair:
    public_key: str
    secret_key: str
    account_id: Optional[str]


def generate_node_keypairs(n: int, rip: Chain) -> List[Keypair]:
    """generate keypairs suitable for validator keys"""
    result = []
    for i in range(n):
        # TODO: do this locally
        req = {
            "id": f"vc_{i}_{n}",
            "command": "validation_create",
        }
        keys = rip.request_json(req)
        result.append(
            Keypair(
                public_key=keys["validation_public_key"],
                secret_key=keys["validation_seed"],
                account_id=None,
            )
        )
    return result


def generate_federator_keypairs(n: int, rip: Chain) -> List[Keypair]:
    """generate keypairs suitable for federator keys"""
    result = []
    for i in range(n):
        # TODO: clean this up after the PR gets merged in the C++ code
        wallet = Wallet.create(crypto_algorithm=CryptoAlgorithm.ED25519)
        entropy = decode_seed(wallet.seed)[0]
        result.append(
            Keypair(
                public_key=encode_account_public_key(bytes.fromhex(wallet.public_key)),
                secret_key=_encode(entropy, _FAMILY_SEED_PREFIX, SEED_LENGTH),
                account_id=wallet.classic_address,
            )
        )
    return result


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
    def __init__(
        self, num_nodes: int, num_validators: int, start_cfg_index: int, rip: Chain
    ):
        self.validator_keypairs = generate_node_keypairs(num_validators, rip)
        self.ports = [Ports(start_cfg_index + i) for i in range(num_nodes)]


class SidechainNetwork(Network):
    def __init__(
        self,
        num_nodes: int,
        num_federators: int,
        num_validators: int,
        start_cfg_index: int,
        rip: Chain,
    ):
        super().__init__(num_nodes, num_validators, start_cfg_index, rip)
        self.federator_keypairs = generate_federator_keypairs(num_federators, rip)
        self.main_account = Wallet.create(CryptoAlgorithm.SECP256K1)


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