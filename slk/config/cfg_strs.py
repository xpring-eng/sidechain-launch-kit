"""Helper methods for generating the strings that make up the config files."""

import json
from typing import Any, Dict, List, Optional, Tuple, Union

from xrpl.models import XRP, Amount
from xrpl.wallet import Wallet

from slk.config.helper_classes import Keypair, XChainAsset

FEDERATORS_STANZA_INIT = """
# federator signing public keys
[sidechain_federators]
"""
FEDERATORS_SECRETS_STANZA_INIT = """
# federator signing secret keys (for standalone-mode testing only; Normally won't be in
# a config file)
[sidechain_federators_secrets]
"""
BOOTSTRAP_FEDERATORS_STANZA_INIT = """
# first value is federator signing public key, second is the signing pk account
[sidechain_federators]
"""

THIS_IP = "127.0.0.1"


def _amt_to_json(amt: Amount) -> Union[str, Dict[str, Any]]:
    if isinstance(amt, str):
        return amt
    else:
        return amt.to_dict()


def _generate_asset_stanzas(assets: Optional[Dict[str, XChainAsset]] = None) -> str:
    if assets is None:
        # default to xrp only at a 1:1 value
        assets = {}
        assets["xrp_xrp_sidechain_asset"] = XChainAsset(
            XRP(), XRP(), "1", "1", "400", "400"
        )

    index_stanza = """
[sidechain_assets]"""

    asset_stanzas = []

    for name, xchainasset in assets.items():
        index_stanza += "\n" + name
        new_stanza = f"""
[{name}]
mainchain_asset={json.dumps(_amt_to_json(xchainasset.main_asset))}
sidechain_asset={json.dumps(_amt_to_json(xchainasset.side_asset))}
mainchain_refund_penalty={json.dumps(_amt_to_json(xchainasset.main_refund_penalty))}
sidechain_refund_penalty={json.dumps(_amt_to_json(xchainasset.side_refund_penalty))}"""
        asset_stanzas.append(new_stanza)

    return index_stanza + "\n" + "\n".join(asset_stanzas)


# First element of the returned tuple is the sidechain stanzas
# second element is the bootstrap stanzas
def generate_sidechain_stanza(
    mainchain_url: str,
    main_account: Wallet,
    federators: List[Keypair],
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> Tuple[str, str]:
    """
    Generates the [sidechain] stanza in rippled.cfg and also the [sidechain] stanza in
    the sidechain_bootstrap.cfg file.

    Args:
        mainchain_url: The URL of the mainchain. If the chain is local, it is 127.0.0.1.
        main_account: The Wallet for the door account on the mainchain.
        federators: The federators in the network.
        xchain_assets: Cross-chain asset information.

    Returns:
        The `[sidechain]` stanzas for `rippled.cfg` and `sidechain_bootstrap.cfg`.
    """
    assets_stanzas = _generate_asset_stanzas(xchain_assets)

    federators_stanza = FEDERATORS_STANZA_INIT
    federators_secrets_stanza = FEDERATORS_SECRETS_STANZA_INIT
    bootstrap_federators_stanza = BOOTSTRAP_FEDERATORS_STANZA_INIT

    for fed in federators:
        federators_stanza += f"{fed.public_key}\n"
        federators_secrets_stanza += f"{fed.secret_key}\n"
        bootstrap_federators_stanza += f"{fed.public_key} {fed.account_id}\n"

    sidechain_stanzas = f"""{assets_stanzas}

{federators_stanza}

{federators_secrets_stanza if mainchain_url == THIS_IP else ""}
"""

    bootstrap_stanzas = f"""
[sidechain]
mainchain_secret={main_account.seed}

{bootstrap_federators_stanza}
"""
    return (sidechain_stanzas, bootstrap_stanzas)
