from typing import Literal

import msgspec

CryptoAssetChangeKind = Literal["created", "updated", "deleted"]


class CryptoAssetChange(msgspec.Struct, frozen=True):
    """Событие «у `CryptoAsset` могла измениться подписка» для `stream_binance`."""

    asset_id: int
    kind: CryptoAssetChangeKind
    exchange: str
    trading_pair: str
