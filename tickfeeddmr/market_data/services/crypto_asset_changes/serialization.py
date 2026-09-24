from typing import cast, get_args

from tickfeeddmr.market_data.services.crypto_asset_changes.schemas import (
    CryptoAssetChange,
    CryptoAssetChangeKind,
)

MALFORMED_ASSET_CHANGE_ERRORS = (KeyError, ValueError)

_KINDS = frozenset(get_args(CryptoAssetChangeKind))


def serialize_crypto_asset_change(change: CryptoAssetChange) -> dict[str, str]:
    """`CryptoAssetChange` -> плоский dict строк для `XADD`."""
    return {
        "asset_id": str(change.asset_id),
        "kind": change.kind,
        "exchange": change.exchange,
        "trading_pair": change.trading_pair,
    }


def deserialize_crypto_asset_change(fields: dict[str, str]) -> CryptoAssetChange:
    """Обратное преобразование к `serialize_crypto_asset_change`.

    Бросает один из `MALFORMED_ASSET_CHANGE_ERRORS` на отсутствующих или
    битых полях — вызывающий код сам решает, что делать с такой записью.
    """
    kind = fields["kind"]
    if kind not in _KINDS:
        msg = f"Неизвестный kind события CryptoAsset: {kind!r}"
        raise ValueError(msg)
    return CryptoAssetChange(
        asset_id=int(fields["asset_id"]),
        kind=cast("CryptoAssetChangeKind", kind),
        exchange=fields["exchange"],
        trading_pair=fields["trading_pair"],
    )
