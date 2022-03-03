"""Helper methods for generating the strings that make up the config files."""

from typing import Dict, List, Optional

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

THIS_IP = "127.0.0.1"


# First element of the returned tuple is the sidechain stanzas
# second element is the bootstrap stanzas
def generate_sidechain_stanza(
    mainchain_url: str,
    main_account: Wallet,
    federators: List[Keypair],
    xchain_assets: Optional[Dict[str, XChainAsset]] = None,
) -> str:
    """
    Generates the [sidechain] stanza in rippled.cfg.

    Args:
        mainchain_url: The URL of the mainchain. If the chain is local, it is 127.0.0.1.
        main_account: The Wallet for the door account on the mainchain.
        federators: The federators in the network.
        xchain_assets: Cross-chain asset information.

    Returns:
        The `[sidechain]` stanzas for `rippled.cfg`.
    """
    federators_stanza = FEDERATORS_STANZA_INIT
    federators_secrets_stanza = FEDERATORS_SECRETS_STANZA_INIT

    for fed in federators:
        federators_stanza += f"{fed.public_key}\n"
        federators_secrets_stanza += f"{fed.secret_key}\n"

    sidechain_stanzas = f"""{federators_stanza}

{federators_secrets_stanza if mainchain_url == THIS_IP else ""}
"""
    return sidechain_stanzas
