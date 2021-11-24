"""A class that stores token information in easily-accessible ways."""

from __future__ import annotations

from typing import Dict, List, Optional

from tabulate import tabulate
from xrpl.models import IssuedCurrency


class AssetAliases:
    """A class that stores token information in easily-accessible ways."""

    def __init__(self: AssetAliases) -> None:
        """Initialize an AssetAliases."""
        self._aliases: Dict[str, IssuedCurrency] = {}  # alias -> IssuedCurrency

    def add(self: AssetAliases, asset: IssuedCurrency, name: str) -> None:
        self._aliases[name] = asset

    def is_alias(self: AssetAliases, name: str) -> bool:
        return name in self._aliases

    def asset_from_alias(self: AssetAliases, name: str) -> IssuedCurrency:
        assert name in self._aliases
        return self._aliases[name]

    def known_aliases(self: AssetAliases) -> List[str]:
        return list(self._aliases.keys())

    def known_assets(self: AssetAliases) -> List[IssuedCurrency]:
        return list(self._aliases.values())

    def to_string(self: AssetAliases, nickname: Optional[str] = None) -> str:
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
