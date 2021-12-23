"""A class that stores token information in easily-accessible ways."""

from __future__ import annotations

from typing import Dict, List, Optional

from tabulate import tabulate
from xrpl.models import IssuedCurrency


class AssetAliases:
    """
    A class that stores token information in easily-accessible ways.

    This is a helper class for chains, and is used extensively by the REPL.
    """

    def __init__(self: AssetAliases) -> None:
        """Initialize an AssetAliases."""
        self._aliases: Dict[str, IssuedCurrency] = {}  # alias -> IssuedCurrency

    def add(self: AssetAliases, asset: IssuedCurrency, name: str) -> None:
        """
        Add an asset with the given name.

        Args:
            asset: The token to add.
            name: The token's nickname.
        """
        self._aliases[name] = asset

    def is_alias(self: AssetAliases, name: str) -> bool:
        """
        Determine whether an asset name is a known asset.

        Args:
            name: The token's nickname.

        Returns:
            True if the asset name is a known asset. False otherwise.
        """
        return name in self._aliases

    def asset_from_alias(self: AssetAliases, name: str) -> IssuedCurrency:
        """
        Get the asset information for a given alias.

        Args:
            name: The token's nickname.

        Returns:
            The token associated with the given nicknamme.
        """
        assert name in self._aliases
        return self._aliases[name]

    def known_aliases(self: AssetAliases) -> List[str]:
        """
        Return a list of all known aliases for the assets.

        Returns:
            A list of all known aliases for the assets.
        """
        return list(self._aliases.keys())

    def known_assets(self: AssetAliases) -> List[IssuedCurrency]:
        """
        Return a list of all known assets.

        Returns:
            A list of all known assets.
        """
        return list(self._aliases.values())

    def to_string(self: AssetAliases, nickname: Optional[str] = None) -> str:
        """
        Return a string representation of the assets.

        Args:
            nickname: Nickname of the token to get information about. The default is
                None. When set to None, returns a string with information of all tokens.

        Returns:
            A string representation of the token(s).
        """
        # TODO: use asset_from_alias instead of to_string(nickname)
        data = []
        if nickname:
            if nickname in self._aliases:
                v = self._aliases[nickname]
                currency = v.currency
                issuer = v.issuer if v.issuer else ""
            else:
                currency = "NA"
                issuer = "NA"
            data.append(
                {
                    "name": nickname,
                    "currency": currency,
                    "issuer": issuer,
                }
            )
        else:
            for (k, v) in self._aliases.items():
                data.append(
                    {
                        "name": k,
                        "currency": v.currency,
                        "issuer": v.issuer if v.issuer else "",
                    }
                )
        return tabulate(
            data,
            headers="keys",
            tablefmt="presto",
        )
